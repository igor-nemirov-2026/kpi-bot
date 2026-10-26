"""Расчёт KPI: планы на день/неделю/месяц/год, факт, прогнозы, светофоры, зона внимания."""
from __future__ import annotations

import datetime as dt
import re
from calendar import monthrange

MONTH_NAMES = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август",
               "сентябрь", "октябрь", "ноябрь", "декабрь"]
ROLE_NAMES = {"cfo": "CFO", "owner": "Собственник", "sales": "Коммерция", "purchase": "Закупки"}

KEYS = ["day", "day_plan", "week", "week_plan", "mtd", "mtd_plan", "month_plan", "year_plan",
        "ytd", "ytd_plan", "fc_month", "fc_year", "ly_mtd"]


class Engine:
    def __init__(self, data: dict, report_date: dt.date | None = None):
        self.d = data
        self.k = {k["id"]: k for k in data["kpis"]}
        s = data["settings"]
        self.green = float(s.get("Порог_зелёный") or 1.0)
        self.yellow = float(s.get("Порог_жёлтый") or 0.95)
        self.year = int(s.get("Год") or dt.date.today().year)

        rd = report_date or s.get("Дата_отчета")
        if isinstance(rd, dt.datetime):
            rd = rd.date()
        if not rd:
            # дата отчёта = последний день, за который загружена хотя бы половина ежедневных показателей
            # (защита от неполной выгрузки: если 1С прислала только часть цифр за сегодня, берём вчера)
            counts: dict = {}
            for series in data["daily"].values():
                for day in series:
                    counts[day] = counts.get(day, 0) + 1
            if not counts:
                raise ValueError("В листе Факт_дни нет ни одной даты — нечего считать.")
            need = max(counts.values()) * 0.5
            rd = max(day for day, n in counts.items() if n >= need)
        self.R = rd
        self.m = rd.month
        self._memo: dict[str, dict] = {}

        # календарь
        w = data["weights"]
        def weight(day: dt.date) -> float:
            if day in w:
                return w[day]
            return 1.0 if day.weekday() < 5 else 0.0
        self.w = weight
        self.mdays = {mm: [dt.date(self.year, mm, i) for i in range(1, monthrange(self.year, mm)[1] + 1)] for mm in range(1, 13)}
        self.Wm = {mm: sum(weight(x) for x in self.mdays[mm]) or 1.0 for mm in range(1, 13)}
        self.We = sum(weight(x) for x in self.mdays[self.m] if x <= rd)
        self.Wleft = self.Wm[self.m] - self.We
        self.week = [rd - dt.timedelta(days=rd.weekday()) + dt.timedelta(days=i) for i in range(7)]
        self.week = [x for x in self.week if x <= rd]
        self.Wweek = sum(weight(x) for x in self.week) or 1.0
        self.Wyear = sum(self.Wm.values())
        self.Wytd = sum(self.Wm[mm] for mm in range(1, self.m)) + self.We
        self.wd_month = sum(1 for x in self.mdays[self.m] if weight(x) > 0)
        self.wd_elapsed = sum(1 for x in self.mdays[self.m] if weight(x) > 0 and x <= rd)

    # ---------- helpers ----------
    def plan(self, kid, mm):
        return self.d["plan"].get(kid, {}).get(mm)

    def day_plan(self, kid, day):
        p = self.plan(kid, day.month)
        return None if p is None else p * self.w(day) / self.Wm[day.month]

    def is_flow(self, kid) -> bool:
        k = self.k[kid]
        if k["type"] == "sum":
            return True
        if k["type"] == "formula":
            refs = re.findall(r"\{(\w+)\}", k["formula"])
            return "/" not in k["formula"] and "ANN" not in k["formula"] and all(self.is_flow(r) for r in refs if r in self.k)
        return False

    def closed_month(self, kid, mm):
        """Факт закрытого месяца: лист Факт_месяцы, иначе из Факт_дни."""
        v = self.d["fact_m"].get(kid, {}).get(mm)
        if v is not None:
            return v
        days = {d: x for d, x in self.d["daily"].get(kid, {}).items() if d.year == self.year and d.month == mm}
        if not days:
            return None
        if self.k[kid]["type"] == "sum":
            return sum(days.values())
        if self.k[kid]["type"] == "avg":
            return sum(days.values()) / len(days)
        return days[max(days)]

    def _agg(self, kid, vals: dict):
        if not vals:
            return None
        t = self.k[kid]["type"]
        if t == "sum":
            return sum(vals.values())
        if t == "avg":
            return sum(vals.values()) / len(vals)
        return vals[max(vals)]

    # ---------- base KPI ----------
    def _base(self, kid) -> dict:
        k, R, m = self.k[kid], self.R, self.m
        daily = self.d["daily"].get(kid, {})
        weekly = self.d["weekly"].get(kid, {})
        plans = [self.plan(kid, mm) for mm in range(1, 13)]
        out = dict.fromkeys(KEYS)
        out["month_plan"] = plans[m - 1]
        closed = [self.closed_month(kid, mm) for mm in range(1, m)]
        ly = self.d["last_year"].get(kid, {}).get(m)

        if k["type"] == "sum":
            out["day"] = daily.get(R)
            out["day_plan"] = self.day_plan(kid, R)
            wv = {x: daily[x] for x in self.week if x in daily}
            out["week"] = sum(wv.values()) if wv else None
            wp = [self.day_plan(kid, x) for x in self.week]
            out["week_plan"] = None if any(p is None for p in wp) else sum(wp)
            mv = {x: v for x, v in daily.items() if x.year == self.year and x.month == m and x <= R}
            out["mtd"] = sum(mv.values()) if mv else None
            mp = plans[m - 1]
            out["mtd_plan"] = None if mp is None else mp * self.We / self.Wm[m]
            out["year_plan"] = sum(p for p in plans if p is not None) if any(p is not None for p in plans) else None
            if out["mtd"] is not None and self.We > 0:
                out["fc_month"] = out["mtd"] / self.We * self.Wm[m]
            known_closed = [c for c in closed if c is not None]
            if known_closed or out["mtd"] is not None:
                out["ytd"] = sum(known_closed) + (out["mtd"] or 0)
            ytdp = [plans[i] for i in range(m - 1)]
            if all(p is not None for p in ytdp) and out["mtd_plan"] is not None:
                out["ytd_plan"] = sum(ytdp) + out["mtd_plan"]
            if out["ytd"] is not None and out["ytd_plan"]:
                kf = out["ytd"] / out["ytd_plan"]
                cur = out["fc_month"] if out["fc_month"] is not None else (mp or 0) * kf
                fut = sum((plans[i] or 0) for i in range(m, 12)) * kf
                out["fc_year"] = sum(known_closed) + cur + fut
            out["ly_mtd"] = None if ly is None else ly * self.We / self.Wm[m]
        else:  # avg / last
            out["day"] = daily.get(R)
            out["day_plan"] = plans[m - 1] if out["day"] is not None else None
            wv = {x: daily[x] for x in self.week if x in daily}
            if wv:
                out["week"] = self._agg(kid, wv)
            else:
                monday = R - dt.timedelta(days=R.weekday())
                cands = {x: v for x, v in weekly.items() if monday - dt.timedelta(days=7) <= x <= R}
                out["week"] = cands[max(cands)] if cands else None
            out["week_plan"] = plans[m - 1] if out["week"] is not None else None
            mv = {x: v for x, v in daily.items() if x.year == self.year and x.month == m and x <= R}
            if not mv:
                mv = {x: v for x, v in weekly.items() if x.year == self.year and x.month == m and x <= R}
            out["mtd"] = self._agg(kid, mv)
            out["mtd_plan"] = plans[m - 1]
            known_plans = [p for p in plans if p is not None]
            if k["type"] == "avg":
                out["year_plan"] = sum(known_plans) / len(known_plans) if known_plans else None
                vals = [c for c in closed if c is not None] + ([out["mtd"]] if out["mtd"] is not None else [])
                out["ytd"] = sum(vals) / len(vals) if vals else None
                yp = [p for p in plans[:m] if p is not None]
                out["ytd_plan"] = sum(yp) / len(yp) if yp else None
                out["fc_month"] = out["mtd"]
                if vals:
                    rest = [out["fc_month"]] * (12 - m) if out["fc_month"] is not None else []
                    allv = vals + rest
                    out["fc_year"] = sum(allv) / len(allv)
            else:
                out["year_plan"] = plans[11] if plans[11] is not None else (known_plans[-1] if known_plans else None)
                last_closed = next((c for c in reversed(closed) if c is not None), None)
                out["ytd"] = out["mtd"] if out["mtd"] is not None else last_closed
                out["ytd_plan"] = plans[m - 1]
                out["fc_month"] = out["mtd"]
                out["fc_year"] = out["mtd"]
            out["ly_mtd"] = ly
        return out

    # ---------- formula KPI ----------
    def ann(self, key):
        return {
            "day": self.Wyear / (self.w(self.R) or 1), "day_plan": self.Wyear / (self.w(self.R) or 1),
            "week": self.Wyear / self.Wweek, "week_plan": self.Wyear / self.Wweek,
            "mtd": self.Wyear / (self.We or 1), "mtd_plan": self.Wyear / (self.We or 1), "ly_mtd": self.Wyear / (self.We or 1),
            "month_plan": self.Wyear / self.Wm[self.m], "fc_month": self.Wyear / self.Wm[self.m],
            "ytd": self.Wyear / (self.Wytd or 1), "ytd_plan": self.Wyear / (self.Wytd or 1),
            "year_plan": 1.0, "fc_year": 1.0,
        }[key]

    @staticmethod
    def evaluate(expr: str, values: dict, ann: float):
        def sub(mt):
            v = values.get(mt.group(1))
            if v is None:
                raise KeyError
            return f"({v!r})"
        try:
            e = re.sub(r"\{(\w+)\}", sub, expr).replace("ANN", repr(ann))
        except KeyError:
            return None
        if not re.fullmatch(r"[0-9eE+\-*/(). ]+", e):
            raise ValueError(f"Недопустимая формула: {expr}")
        try:
            return eval(e, {"__builtins__": {}}, {})  # только числа и + - * / ( )
        except ZeroDivisionError:
            return None

    def values(self, kid) -> dict:
        if kid in self._memo:
            return self._memo[kid]
        if kid not in self.k:
            raise ValueError(f"Формула ссылается на неизвестный kpi_id «{kid}»")
        k = self.k[kid]
        if k["type"] != "formula":
            res = self._base(kid)
        else:
            refs = set(re.findall(r"\{(\w+)\}", k["formula"]))
            comp = {r: self.values(r) for r in refs}
            res = {}
            for key in KEYS:
                res[key] = self.evaluate(k["formula"], {r: comp[r][key] for r in refs}, self.ann(key))
            # явный план на формульный KPI перекрывает расчётный
            if kid in self.d["plan"]:
                mp = self.plan(kid, self.m)
                if mp is not None:
                    for key in ("day_plan", "week_plan", "mtd_plan", "month_plan"):
                        res[key] = mp
        self._memo[kid] = res
        return res

    # ---------- status ----------
    def att(self, fact, plan, direction):
        if fact is None or plan is None or fact == 0 or plan == 0:
            return None
        return plan / fact if direction == "down" else fact / plan

    def light(self, x):
        if x is None:
            return "na"
        return "green" if x >= self.green else "yellow" if x >= self.yellow else "red"

    def row(self, kid) -> dict:
        k, v = self.k[kid], self.values(kid)
        flow = self.is_flow(kid)
        a = lambda f, p: self.att(v[f], v[p], k["dir"])
        fm, fy = a("fc_month", "month_plan"), a("fc_year", "year_plan")
        yoy = None
        if v["mtd"] is not None and v["ly_mtd"]:
            yoy = v["mtd"] / v["ly_mtd"] - 1 if flow else v["mtd"] - v["ly_mtd"]
        need = run = None
        if flow and v["mtd"] is not None:
            run = v["mtd"] / self.We if self.We else None
            if k["dir"] == "up" and v["month_plan"] is not None and self.Wleft > 0:
                need = max(0.0, (v["month_plan"] - v["mtd"]) / self.Wleft)
        return {
            "id": kid, "kpi": k["name"], "section": k["section"], "unit": k["unit"], "dir": k["dir"],
            "kind": "flow" if flow else "level", "best": k["best"], "definition": k["definition"],
            "source": k["source"], "owner": k["owner"],
            **{key: v[key] for key in KEYS},
            "day_pct": a("day", "day_plan"), "week_pct": a("week", "week_plan"), "mtd_pct": a("mtd", "mtd_plan"),
            "ytd_pct": a("ytd", "ytd_plan"), "fc_month_pct": fm, "fc_year_pct": fy,
            "light_month": self.light(fm), "light_year": self.light(fy), "yoy": yoy,
            "need_day": need, "run_day": run,
        }

    # ---------- series for charts ----------
    def daily_series(self, kid):
        """Нарастающий итог месяца по дням: план, факт, прогноз по темпу."""
        k = self.k[kid]
        refs = re.findall(r"\{(\w+)\}", k["formula"]) if k["type"] == "formula" else [kid]
        def day_val(ref, x):
            return self.d["daily"].get(ref, {}).get(x)
        rows, pc, fc_ = [], 0.0, 0.0
        mtd_total = None
        rate = None
        v = self.values(kid)
        if v["mtd"] is not None and self.We:
            rate = v["mtd"] / self.We
        for x in self.mdays[self.m]:
            if self.w(x) == 0:
                continue
            if k["type"] == "formula":
                comp_plan = {r: self.day_plan(r, x) for r in refs}
                comp_fact = {r: day_val(r, x) for r in refs}
                p = self.evaluate(k["formula"], comp_plan, 1.0)
                f = self.evaluate(k["formula"], comp_fact, 1.0) if x <= self.R else None
            else:
                p, f = self.day_plan(kid, x), (day_val(kid, x) if x <= self.R else None)
            pc += p or 0
            row = {"date": x.isoformat(), "plan_cum": round(pc, 3), "fact_cum": None, "forecast_cum": None}
            if x <= self.R:
                fc_ += f or 0
                row["fact_cum"] = round(fc_, 3)
                mtd_total = fc_
            elif rate is not None and mtd_total is not None:
                mtd_total += rate * self.w(x)
                row["forecast_cum"] = round(mtd_total, 3)
            rows.append(row)
        # точка стыка факта и прогноза
        for i, r in enumerate(rows):
            if r["date"] == max((x["date"] for x in rows if x["fact_cum"] is not None), default=None):
                r["forecast_cum"] = r["fact_cum"]
        return rows

    def monthly_series(self, kid):
        k = self.k[kid]
        refs = re.findall(r"\{(\w+)\}", k["formula"]) if k["type"] == "formula" else [kid]
        base = {}
        for r in refs:
            vr = self.values(r)
            kf = (vr["ytd"] / vr["ytd_plan"]) if vr["ytd"] is not None and vr["ytd_plan"] else 1.0
            ser = []
            for mm in range(1, 13):
                p = self.plan(r, mm)
                if mm < self.m:
                    f, fc = self.closed_month(r, mm), None
                elif mm == self.m:
                    f, fc = vr["mtd"], vr["fc_month"]
                else:
                    f, fc = None, (None if p is None else p * kf)
                ser.append({"plan": p, "fact": f, "forecast": fc, "last_year": self.d["last_year"].get(r, {}).get(mm)})
            base[r] = ser
        out = []
        for i in range(12):
            row = {"month": f"{self.year}-{i + 1:02d}"}
            for f in ("plan", "fact", "forecast", "last_year"):
                vals = {r: base[r][i][f] for r in refs}
                if k["type"] == "formula":
                    val = self.evaluate(k["formula"], vals, 1.0)
                else:
                    val = vals[kid]
                row[f] = None if val is None else round(val, 3)
            out.append(row)
        return out

    # ---------- alerts ----------
    @staticmethod
    def fmt(v, d=1):
        if v is None:
            return "—"
        s = f"{v:,.{d}f}".replace(",", " ").replace(".", ",")
        return s

    def dec(self, unit):
        return {"x": 2, "ТТ": 0, "т": 0, "чел": 0, "шт": 0}.get(unit, 1)

    def alerts(self, rows):
        out = []
        for r in rows:
            if not (r["light_month"] in ("red", "yellow") or r["light_year"] == "red"):
                continue
            d = self.dec(r["unit"])
            if r["kind"] == "flow" and r["dir"] == "up" and r["fc_month"] is not None:
                gap = (r["month_plan"] or 0) - r["fc_month"]
                text = (f"прогноз месяца {self.fmt((r['fc_month_pct'] or 0) * 100)}% плана, не хватает "
                        f"{self.fmt(gap, d)} {r['unit']}. Нужно {self.fmt(r['need_day'], d)} в день против {self.fmt(r['run_day'], d)} сейчас.")
            elif r["kind"] == "flow" and r["fc_month"] is not None:
                text = (f"прогноз месяца {self.fmt(r['fc_month'], d)} при плане {self.fmt(r['month_plan'], d)} {r['unit']}, "
                        f"превышение {self.fmt(r['fc_month'] - (r['month_plan'] or 0), d)}.")
            else:
                u = {"%": "%", "дни": " дн.", "x": "x"}.get(r["unit"], " " + r["unit"])
                dd = 2 if r["unit"] == "%" and abs(r["month_plan"] or 10) < 1 else d
                if dd == 0 and abs(r["month_plan"] or 1000) < 100:
                    dd = 1
                best = r["best"].rstrip(".")
                base = f"сейчас {self.fmt(r['fc_month'], dd)}{u} при цели {self.fmt(r['month_plan'], dd)}{u}".rstrip(".")
                text = base + (f". Ориентир: {best}." if best else ".")
            light = "red" if "red" in (r["light_month"], r["light_year"]) else "yellow"
            score = r["fc_month_pct"] if r["fc_month_pct"] is not None else (r["fc_year_pct"] or 1)
            out.append({"id": r["id"], "kpi": r["kpi"], "light": light, "score": score, "text": text})
        out.sort(key=lambda a: (a["light"] != "red", a["score"]))
        return out

    # ---------- role report ----------
    def role_report(self, role: str, charts: dict) -> dict:
        ids = [k["id"] for k in self.d["kpis"] if role in k["roles"]]
        rows = [self.row(i) for i in ids]
        for r in rows:
            r["tile"] = role in self.k[r["id"]]["tile_roles"]
        summary = {c: sum(1 for r in rows if r["light_month"] == c) for c in ("green", "yellow", "red")}
        summary["total"] = len(rows)
        ch = {}
        if charts.get("daily") in self.k:
            kd = charts["daily"]
            ch["daily"] = {"metric": kd, "name": self.k[kd]["name"], "unit": self.k[kd]["unit"], "rows": self.daily_series(kd)}
        if charts.get("monthly") in self.k:
            km = charts["monthly"]
            ch["monthly"] = {"metric": km, "name": self.k[km]["name"], "unit": self.k[km]["unit"], "rows": self.monthly_series(km)}
        return {"role": role, "role_name": ROLE_NAMES.get(role, role), "summary": summary,
                "kpis": [_round(r) for r in rows], "alerts": self.alerts(rows), "charts": ch}

    def meta(self) -> dict:
        monday = self.R - dt.timedelta(days=self.R.weekday())
        return {
            "report_date": self.R.isoformat(),
            "month_name": f"{MONTH_NAMES[self.m - 1].capitalize()} {self.year}",
            "week_label": f"Неделя {self.R.isocalendar()[1]} ({monday:%d.%m}–{self.R:%d.%m})",
            "wd_month": self.wd_month, "wd_elapsed": self.wd_elapsed, "wd_left": self.wd_month - self.wd_elapsed,
            "thresholds": {"green": self.green, "yellow": self.yellow},
        }


def _round(r: dict) -> dict:
    out = {}
    for key, v in r.items():
        out[key] = round(v, 4) if isinstance(v, float) else v
    return out
