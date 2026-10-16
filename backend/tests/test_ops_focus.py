"""
Operator focus system (Phase 4, 16 Oct 2026): services/ops_copy.py, ops_focus.py,
hot_signal.py, lead_watch.py, client_shortlist.py.

No real database: a FakeConn answers exactly the statements the services issue
(matched against the modules' own SQL constants) from in-memory lists.

Run:  cd backend && venv/bin/python -m pytest tests/test_ops_focus.py -q --noconftest
"""
import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ops-focus")

import db_pool  # noqa: E402,F401  (backend/db_pool before ai/ shadows it)

import types  # noqa: E402

_BACKEND_INIT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "__init__.py")
if "backend" not in sys.modules:
    _stub = types.ModuleType("backend")
    _stub.__file__ = _BACKEND_INIT
    _stub.__path__ = [os.path.dirname(_BACKEND_INIT)]
    sys.modules["backend"] = _stub

import pytest  # noqa: E402

from services import client_shortlist, hot_signal, lead_watch, ops_copy, ops_focus  # noqa: E402
from services.ops_copy import check_draft_copy  # noqa: E402

MON = date(2026, 10, 12)       # Monday
FRI = date(2026, 10, 16)
SAT = date(2026, 10, 17)
SUN = date(2026, 10, 18)


def run(coro):
    return asyncio.run(coro)


def _norm(s):
    return " ".join(s.split())


# ---------------------------------------------------------------------------
# Fake connection for build_focus / mark_done
# ---------------------------------------------------------------------------
class FakeConn:
    def __init__(self):
        self.hot = []
        self.msgs = []
        self.jobs = []
        self.wins = []
        self.leads = []
        self.watches = []
        self.matches = {}          # watch_id -> rows
        self.shortlist = None      # {"drafts": n, "total": m}
        self.touch = []
        self.suppressed = set()
        self.state = {}            # key -> dict
        self.executed = []
        self.shown = []
        self.sent = []             # ops_sent_emails rows (manual)

    async def fetchval(self, sql, *a):
        n = _norm(sql)
        if n == _norm(hot_signal.SQL_HAS_USER_BEHAVIOR):
            return True
        if n == _norm(ops_focus.SQL_MARK_DONE):
            self.executed.append((n, a))
            if self.state.get(a[0], {}).get("status") == "done":
                return None
            self.state[a[0]] = {"kind": a[1], "status": "done", "done_via": a[2],
                                "done_at": datetime.now(timezone.utc), "snoozed_until": None,
                                "title_snapshot": a[4]}
            return a[0]
        raise AssertionError(f"unexpected fetchval {sql[:80]}")

    async def fetch(self, sql, *a):
        n = _norm(sql)
        if n in (_norm(hot_signal.SQL_SIGNALS), _norm(hot_signal.SQL_SIGNALS_NO_VIEWS)):
            return list(self.hot)
        if n == _norm(ops_focus.SQL_CLIENT_MESSAGES):
            return list(self.msgs)
        if n == _norm(ops_focus.SQL_JOBS):
            return list(self.jobs)
        if n == _norm(ops_focus.SQL_WINS):
            return list(self.wins)
        if n == _norm(ops_focus.SQL_LEADS):
            return list(self.leads)
        if n == _norm(lead_watch.SQL_DUE):
            return list(self.watches)
        if n == _norm(lead_watch.SQL_NEW_MATCHES):
            return list(self.matches.get(a[4], []))
        if n == _norm(ops_focus.SQL_CLIENT_TOUCH):
            return list(self.touch)
        if n == _norm(ops_focus.SQL_SUPPRESSED):
            return [{"email": e} for e in a[0] if e in self.suppressed]
        if n == _norm(ops_focus.SQL_STATES):
            return [dict(self.state[k], key=k) for k in a[0] if k in self.state]
        if n == _norm(ops_focus.SQL_HIDDEN_GOBACK):
            return [{"key": k} for k, v in self.state.items() if k.startswith("goback:") and (
                v["status"] == "done" or (v["status"] == "snoozed" and v.get("snoozed_until")
                                          and v["snoozed_until"] > a[0]))]
        if n == _norm(ops_focus.SQL_DONE_TODAY):
            return [dict(v, key=k) for k, v in self.state.items()
                    if v["status"] == "done" and v.get("done_at") and v["done_at"] >= a[0]]
        raise AssertionError(f"unexpected fetch {n[:100]}")

    async def fetchrow(self, sql, *a):
        n = _norm(sql)
        if n == _norm(ops_focus.SQL_SHORTLIST_DRAFTS):
            return self.shortlist
        if n == _norm(ops_focus.SQL_STATE_ONE):
            s = self.state.get(a[0])
            return dict(s, key=a[0]) if s else None
        if n in (_norm(lead_watch.SQL_WATCH_ONE), _norm(lead_watch.SQL_WATCH_BY_EMAIL)):
            for w in self.watches:
                if str(w["id"]) == str(a[0]) or w.get("email") == a[0]:
                    return dict(w, active=w.get("active", True), replied_at=w.get("replied_at"))
            return None
        if n == _norm(lead_watch.SQL_TOUCH):
            for w in self.watches:
                if str(w["id"]) == str(a[0]):
                    w["touch_count"] += 1
                    w["last_touched_at"] = a[1]
                    return {"cadence_days": [3, 7, 14], "cadence_repeat_days": 21,
                            "touch_count": w["touch_count"]}
            return None
        raise AssertionError(f"unexpected fetchrow {n[:100]}")

    async def execute(self, sql, *a):
        n = _norm(sql)
        self.executed.append((n, a))
        if n == _norm(ops_focus.SQL_SNOOZE):
            self.state[a[0]] = {"kind": a[1], "status": "snoozed", "snoozed_until": a[2],
                                "done_at": None, "done_via": None, "title_snapshot": a[3]}
        elif n == _norm(ops_focus.SQL_REOPEN):
            if a[0] in self.state:
                self.state[a[0]].update(status="open", done_at=None, snoozed_until=None)
        elif n == _norm(ops_focus.SQL_LEAD_CONTACTED):
            for l in self.leads:
                if str(l["id"]) == str(a[0]) and l["status"] == "new":
                    l["status"] = "contacted"
            self.leads = [l for l in self.leads if l["status"] == "new"]
        elif n == _norm(ops_focus.SQL_LEADS_CONTACTED_BY_EMAIL):
            for l in self.leads:
                if l["email"].lower() == a[0] and l["status"] == "new":
                    l["status"] = "contacted"
            self.leads = [l for l in self.leads if l["status"] == "new"]
        elif n == _norm(ops_focus.SQL_MANUAL_SENT):
            self.sent.append({"dedupe_key": a[0], "kind": a[1], "to_email": a[2], "channel": "manual"})
        elif n.startswith("UPDATE lead_watches SET follow_up_due"):
            pass
        return "UPDATE 1"

    async def executemany(self, sql, rows):
        self.shown.extend(rows)


def tender(tid="17400/2026", days=10, today=FRI, **kw):
    d = {"tender_id": tid, "title": "Одржување на софтвер за субвенции",
         "procuring_entity": "Министерство за економија", "closing_date": today + timedelta(days=days),
         "estimated_value_mkd": 400000, "t_status": "open", "procedure_type": "Отворена постапка"}
    d.update(kw)
    return d


def hot_row(email="marija@firma.mk", acct="prospect", **kw):
    r = tender(**kw)
    now = datetime.now(timezone.utc)
    r.update(user_id=uuid.uuid4(), email=email, full_name="Марија Петровска",
             company_name="Софтвер Плус ДООЕЛ", account_type=acct,
             first_at=now - timedelta(hours=5), last_at=now - timedelta(hours=2), n_views=3, n_asks=1)
    return r


def lead_row(email="info@gradba.mk", **kw):
    r = tender(**kw)
    r.update(id=uuid.uuid4(), email=email, company_name="Градба ДОО", lead_person="Петар Николовски",
             wants_to_win="одржување софтвер, ГИС", source="usluga", status="new", user_id=None)
    return r


# ---------------------------------------------------------------------------
# Copy rules
# ---------------------------------------------------------------------------
def all_templates():
    t = tender()
    job = dict(t, id=uuid.uuid4(), user_id=uuid.uuid4(), email="klient@firma.mk",
               full_name="Ана Стојанова", company_name="Фирма ДООЕЛ", invoice_number="12/2026")
    watch = {"id": uuid.uuid4(), "email": "x@y.mk", "person_name": "Иван Иванов", "source": "lead",
             "touch_count": 0, "anchor_at": datetime.now(timezone.utc)}
    matches = [dict(tender(), hit_keywords=["софтвер"]),
               dict(tender("17401/2026", 20), hit_keywords=["софтвер"])]
    sl = {"email": "k@firma.mk", "subject": "Тендери избрани за Фирма ДООЕЛ",
          "intro_text": client_shortlist.default_intro({"full_name": "Ана Стојанова"})}
    items = [dict(tender(), picked=True, note="Ова е токму Вашата дејност."),
             dict(tender("17402/2026"), picked=True, note=None),
             dict(tender("17403/2026"), picked=False, note=None)]
    return {
        "hot_prospect": hot_signal.signal_draft(hot_row()),
        "hot_client": hot_signal.signal_draft(hot_row(acct="managed_client")),
        "lead_open": ops_focus.draft_lead_reply(lead_row(), True),
        "lead_closed": ops_focus.draft_lead_reply(lead_row(), False),
        "payment_check": ops_focus.draft_payment_check(job),
        "checkout": ops_focus.draft_checkout_help(job),
        "submit": ops_focus.draft_submit_reminder(job),
        "review": ops_focus.draft_review_reminder(job),
        "goback_company_only": lead_watch.follow_up_draft(
            dict(watch, person_name=None, company_name="Градба ДОО"), matches[:1]),
        "goback": lead_watch.follow_up_draft(watch, matches),
        "goback_prospect": lead_watch.follow_up_draft(dict(watch, source="prospect"), matches[:1]),
        "shortlist": client_shortlist.render_shortlist_email(sl, items),
    }


@pytest.mark.parametrize("name", list(all_templates()))
def test_every_template_passes_copy_check(name):
    d = all_templates()[name]
    text = d["subject"] + "\n" + d["body_text"]
    assert check_draft_copy(text) == [], (name, check_draft_copy(text), text)
    assert d["body_text"].endswith(ops_copy.SIGNATURE)
    assert "400000" not in text and "400.000" not in text   # never the estimated value
    assert d["to"] == d["to"].lower()


@pytest.mark.parametrize("text,code", [
    ("Цената е 30.000 ден. без ДДВ, многу поволно за Вас", "price"),
    ("Цена 500 € по понуда за Вашата фирма денес", "price"),
    ("Попуст од 20 % за Вашата фирма само овој месец", "price"),
    ("Првата понуда е бесплатна за Вашата фирма", "free"),
    ("Ќе Ве повикам утре за да разговараме подетално", "call_promise"),
    ("Ќе ве контактирам телефонски наскоро за детали", "call_promise"),
    ("Добар ден, ова е одличен тендер за Вас \U0001F680", "emoji"),
    ("Здраво, дали ти е интересен овој тендер за фирмата", "informal"),
    ("Hello, we write bids for Macedonian companies, are you interested", "latin_body"),
])
def test_checker_catches_each_code(text, code):
    assert code in check_draft_copy(text)


def test_checker_does_not_flag_dates_or_days():
    assert check_draft_copy("Рок 22.10.2026.\nДенес е добар ден за понуда, имате 5 дена.") == []


# ---------------------------------------------------------------------------
# Cadence
# ---------------------------------------------------------------------------
def test_next_due_walks_cadence_then_repeats():
    a = datetime(2026, 10, 1, 9, tzinfo=timezone.utc)
    assert lead_watch.next_due(a, [3, 7, 14], 21, 0) == date(2026, 10, 4)
    assert lead_watch.next_due(a, [3, 7, 14], 21, 1) == date(2026, 10, 8)
    assert lead_watch.next_due(a, [3, 7, 14], 21, 2) == date(2026, 10, 15)
    assert lead_watch.next_due(a, [3, 7, 14], 21, 3) == date(2026, 10, 22)
    assert lead_watch.next_due(a, [], 0, 5) == date(2026, 10, 22)


def test_shift_to_working_day():
    off = lambda d: ops_copy.off_day(d, [])  # noqa: E731
    assert lead_watch.shift_to_working_day(SAT, off) == date(2026, 10, 19)
    assert lead_watch.shift_to_working_day(FRI, off) == FRI
    hol = lambda d: ops_copy.off_day(d, [{"holiday_until": "2026-10-21"}])  # noqa: E731
    assert lead_watch.shift_to_working_day(SAT, hol) == date(2026, 10, 22)
    assert lead_watch.shift_to_working_day(SAT, lambda d: True, limit=3) == SAT + timedelta(days=3)


# ---------------------------------------------------------------------------
# Manual file, holidays, lookback
# ---------------------------------------------------------------------------
def test_manual_window_and_prefix():
    manual = [{"date": "2026-10-19", "title": "Поднеси 17400", "detail": "до 11:00"},
              {"date": "2026-10-16", "title": "Жалба 14251"},
              {"date": "2026-10-25", "title": "Далеку"},
              {"date": "2026-10-10", "title": "Минато"},
              {"holiday_until": "2026-10-01"}, "junk", {"date": "bad", "title": "x"}]
    items = ops_focus.manual_items(manual, FRI)
    titles = sorted(i["title"] for i in items)
    assert titles == ["[ДЕНЕС] Жалба 14251", "[за 3 дена] Поднеси 17400"]
    today_item = next(i for i in items if i["title"].startswith("[ДЕНЕС]"))
    assert today_item["priority"] == 5 and today_item["group"] == "reminders"
    future = next(i for i in items if i["title"].startswith("[за"))
    assert future["priority"] == 80
    assert future["key"].startswith("manual:2026-10-19:") and len(future["key"].split(":")[2]) == 10


def test_load_manual_missing_or_invalid(tmp_path):
    assert ops_focus.load_manual(str(tmp_path / "nope.json")) == []
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    assert ops_focus.load_manual(str(p)) == []
    p.write_text('{"date": "2026-10-16"}')
    assert ops_focus.load_manual(str(p)) == []


def test_holiday_and_off_day():
    manual = [{"holiday_until": "2026-10-20"}]
    assert ops_focus.holiday_until(manual) == date(2026, 10, 20)
    assert ops_focus.is_off_day(FRI, manual)
    assert ops_focus.is_off_day(date(2026, 10, 20), manual)
    assert not ops_focus.is_off_day(date(2026, 10, 21), manual)
    assert ops_focus.is_off_day(SAT, [])
    assert not ops_focus.is_off_day(FRI, [])


def test_lookback_hours():
    assert hot_signal.lookback_hours(FRI, []) == 48
    assert hot_signal.lookback_hours(date(2026, 10, 19), []) == 96       # Monday
    assert hot_signal.lookback_hours(SUN, []) == 72
    long = [{"holiday_until": "2026-12-31"}]
    assert hot_signal.lookback_hours(date(2026, 12, 31), long) == 48 + 240


# ---------------------------------------------------------------------------
# Collapse, off-day filter, state filter
# ---------------------------------------------------------------------------
def _it(kind, key, email, prio):
    return {"key": key, "kind": kind, "priority": prio, "email": email, "meta": {},
            "tender": None, "title": key}


def test_collapse_per_recipient():
    items = [_it("goback", "goback:w:0", "a@x.mk", 60), _it("lead_untriaged", "lead:1", "a@x.mk", 50),
             _it("hot_signal", "hot:u:1", "a@x.mk", 10), _it("lead_untriaged", "lead:2", "b@x.mk", 50),
             _it("job_payment_check", "job:1:paycheck", "a@x.mk", 36)]
    out = ops_focus.collapse_per_recipient(items)
    keys = [i["key"] for i in out]
    assert keys == ["hot:u:1", "lead:2", "job:1:paycheck"]
    hot = out[0]
    assert sorted(hot["meta"]["collapsed_keys"]) == ["goback:w:0", "lead:1"]


def _full_conn(today):
    c = FakeConn()
    c.hot = [hot_row(today=today)]
    c.leads = [lead_row(today=today)]
    c.msgs = [{"user_id": uuid.uuid4(), "job_id": None, "email": "k@firma.mk", "company_name": "К",
               "full_name": None, "n": 1, "last_id": uuid.uuid4(), "last_at": None,
               "last_body": "Дали е готово?", "tender_id": None, "title": None,
               "procuring_entity": None, "closing_date": None, "estimated_value_mkd": None}]
    now = datetime.now(timezone.utc)
    c.jobs = [dict(tender(today=today, days=2), id=uuid.uuid4(), user_id=uuid.uuid4(), status="approved",
                   email="klient@firma.mk", full_name="Ана Стојанова", company_name="Фирма",
                   created_at=now, updated_at=now),
              dict(tender("1/2026", today=today, days=20), id=uuid.uuid4(), user_id=uuid.uuid4(),
                   status="requested", email="drug@firma.mk", full_name=None, company_name="Друга",
                   created_at=now, updated_at=now)]
    c.wins = [{"id": uuid.uuid4(), "user_id": uuid.uuid4(), "job_id": None, "tender_id": "9/2026",
               "tender_title": "Т", "procuring_entity": "Е", "matched_name": "Фирма",
               "match_score": 0.9, "detected_at": now, "email": "w@firma.mk",
               "company_name": "W", "full_name": None}]
    c.shortlist = {"drafts": 2, "total": 3}
    return c


def test_off_day_kind_filter():
    c = _full_conn(SAT)
    res = run(ops_focus.build_focus(c, SAT, manual=[]))
    assert res["off_day"] is True
    kinds = {i["kind"] for i in res["items"]}
    assert kinds <= ops_focus.OFF_DAY_KINDS
    assert {"hot_signal", "client_message", "job_approved_deadline"} <= kinds
    assert "lead_untriaged" not in kinds and "job_requested" not in kinds


def test_workday_has_all_and_sorted():
    c = _full_conn(FRI)
    res = run(ops_focus.build_focus(c, FRI, manual=[]))
    kinds = [i["kind"] for i in res["items"]]
    for k in ("hot_signal", "client_message", "job_approved_deadline", "job_requested",
              "win_review", "lead_untriaged", "shortlist_curate"):
        assert k in kinds
    prios = [i["priority"] for i in res["items"]]
    assert prios == sorted(prios)
    for it in res["items"]:
        assert ops_focus.KIND_GROUP[it["kind"]] == it["group"]
        assert __import__("re").match(r"^[a-z0-9:_\-]{3,200}$", it["key"]), it["key"]
        for l in it["links"]:
            assert l["href"].startswith("https://nabavkidata.com")


def test_done_and_snoozed_keys_filtered():
    c = _full_conn(FRI)
    res = run(ops_focus.build_focus(c, FRI, manual=[]))
    hot_key = next(i["key"] for i in res["items"] if i["kind"] == "hot_signal")
    win_key = next(i["key"] for i in res["items"] if i["kind"] == "win_review")
    c.state[hot_key] = {"kind": "hot_signal", "status": "done", "done_via": "ui",
                        "done_at": datetime.now(timezone.utc), "snoozed_until": None,
                        "title_snapshot": "x"}
    c.state[win_key] = {"kind": "win_review", "status": "snoozed", "done_at": None, "done_via": None,
                        "snoozed_until": FRI + timedelta(days=2), "title_snapshot": None}
    res2 = run(ops_focus.build_focus(c, FRI, include_done=True, manual=[]))
    keys = [i["key"] for i in res2["items"]]
    assert hot_key not in keys and win_key not in keys
    assert [i["key"] for i in res2["done"]] == [hot_key]
    # snooze expired -> back
    c.state[win_key]["snoozed_until"] = FRI
    res3 = run(ops_focus.build_focus(c, FRI, manual=[]))
    assert win_key in [i["key"] for i in res3["items"]]
    assert res3["done"] == []


def test_suppressed_and_internal_dropped():
    c = _full_conn(FRI)
    c.hot.append(hot_row(email="test@nabavkidata.com"))
    c.suppressed = {"info@gradba.mk"}
    res = run(ops_focus.build_focus(c, FRI, manual=[]))
    emails = {i["email"] for i in res["items"]}
    assert "test@nabavkidata.com" not in emails
    assert not any(i["kind"] == "lead_untriaged" for i in res["items"])


def test_closed_lead_tender_not_offered():
    c = FakeConn()
    c.leads = [lead_row(days=-1)]
    res = run(ops_focus.build_focus(c, FRI, manual=[]))
    it = next(i for i in res["items"] if i["kind"] == "lead_untriaged")
    assert it["tender"] is None
    assert "затворен" in it["detail"]
    assert "17400" not in it["draft"]["body_text"]


def test_mark_done_lead_side_effect_and_idempotent_goback():
    c = FakeConn()
    lead = lead_row()
    c.leads = [lead]
    item = run(ops_focus.mark_done(c, f"lead:{lead['id']}", FRI, "send"))
    assert item["kind"] == "lead_untriaged"
    assert lead["status"] == "contacted"
    assert c.state[f"lead:{lead['id']}"]["status"] == "done"

    wid = uuid.uuid4()
    c.watches = [{"id": wid, "email": "z@firma.mk", "person_name": None, "company_name": "З",
                  "source": "lead", "keywords": ["софтвер"], "touch_count": 0, "user_id": None,
                  "anchor_at": datetime.now(timezone.utc) - timedelta(days=4), "last_touched_at": None,
                  "min_days_to_close": 5, "min_value_mkd": None, "max_value_mkd": None}]
    c.matches[wid] = [dict(tender(), hits=[lead_watch.keyword_pattern("софтвер")])]
    res = run(ops_focus.build_focus(c, FRI, manual=[]))
    gb = next(i for i in res["items"] if i["kind"] == "goback")
    assert gb["key"] == f"goback:{wid}:0"
    run(ops_focus.mark_done(c, gb["key"], FRI, "ui"))
    assert c.watches[0]["touch_count"] == 1
    assert [(str(w), t) for w, t in c.shown] == [(str(wid), "17400/2026")]
    run(ops_focus.mark_done(c, gb["key"], FRI, "ui"))       # second click: no second touch
    assert c.watches[0]["touch_count"] == 1


def test_mark_done_unknown_key_still_writes_state():
    c = FakeConn()
    assert run(ops_focus.mark_done(c, "touch:abc:2026-w42", FRI, "send")) is None
    assert c.state["touch:abc:2026-w42"]["kind"] == "client_touch"
    until = run(ops_focus.snooze(c, "job:x:paycheck", FRI, 3))
    assert until == FRI + timedelta(days=3)
    assert c.state["job:x:paycheck"]["kind"] == "job_payment_check"


def test_goback_nothing_new_is_a_note_not_an_item():
    c = FakeConn()
    c.watches = [{"id": uuid.uuid4(), "email": "z@firma.mk", "keywords": ["софтвер"], "touch_count": 1,
                  "anchor_at": datetime.now(timezone.utc), "last_touched_at": None, "user_id": None,
                  "min_days_to_close": 5, "min_value_mkd": None, "max_value_mkd": None}]
    res = run(ops_focus.build_focus(c, FRI, manual=[]))
    assert not any(i["kind"] == "goback" for i in res["items"])
    assert any("го-бек" in n for n in res["notes"])


def test_job_classification_rules():
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=5)
    base = dict(tender(days=4), id=uuid.uuid4(), user_id=uuid.uuid4(), email="k@f.mk",
                full_name=None, company_name="Ф", created_at=old, updated_at=old, paid_at=old,
                published_at=None, reopen_count=2, invoice_requested_at=None, invoice_issued_at=None,
                invoice_number=None, stripe_checkout_session_id=None)
    kinds = lambda j: sorted(i["kind"] for i in ops_focus.classify_job(j, FRI, now))  # noqa: E731
    assert kinds(dict(base, status="preparing")) == ["job_preparing", "job_preparing_deadline"]
    assert kinds(dict(base, status="changes_requested"))[0] == "job_changes"
    assert ops_focus.classify_job(dict(base, status="changes_requested"), FRI, now)[0]["key"].endswith(":changes:2")
    assert kinds(dict(base, status="payment_required", paid_at=None,
                      invoice_requested_at=old)) == ["job_invoice"]
    assert kinds(dict(base, status="payment_required", invoice_issued_at=old, paid_at=None,
                      invoice_requested_at=old)) == ["job_payment_check"]
    assert kinds(dict(base, status="payment_required", paid_at=None,
                      stripe_checkout_session_id="cs_1")) == ["job_checkout_abandoned"]
    assert kinds(dict(base, status="approved", closing_date=FRI + timedelta(days=9))) == []


# ---------------------------------------------------------------------------
# Greeting, keywords
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,expected", [
    ("Марија Петровска", "Добар ден, Марија,"),
    ("петар", "Добар ден, Петар,"),
    ("Софтвер Плус ДООЕЛ", "Добар ден,"),
    ("ГРАДБА", "Добар ден,"),
    ("Alfa DOO", "Добар ден,"),
    ("ЈЗУ Здравствен дом", "Добар ден,"),
    ("Фирма за градба Скопје Македонија", "Добар ден,"),
    ("Info123", "Добар ден,"),
    ("ana", "Добар ден, Ана,"),                     # Latin-typed name -> Cyrillic
    ("Marija Petrovska", "Добар ден, Марија,"),
    ("Kjiro", "Добар ден, Ќиро,"),
    ("Wesley", "Добар ден,"),                        # not transliterable -> no name
    ("", "Добар ден,"),
    (None, "Добар ден,"),
])
def test_greeting_rejects_company_names(name, expected):
    assert ops_copy.greeting(name) == expected


def test_split_keywords():
    kws = lead_watch.split_keywords("Одржување софтвер, ГИС; тендер 17400/2026 и хостинг / ИТ\nинформациски систем или веб")
    assert kws == ["одржување софтвер", "тендер", "хостинг", "информациски систем"]
    assert lead_watch.split_keywords(None) == []
    assert len(lead_watch.split_keywords(",".join(f"збор{i}" for i in range(30)))) == 10


def test_keyword_patterns():
    pats = lead_watch.keyword_patterns(["софтвер", "ГИС", "c++ (dev)", "софтвер"])
    assert pats[0] == "(^|[^[:alnum:]])софтвер"
    assert pats[1] == "(^|[^[:alnum:]])ГИС($|[^[:alnum:]])"
    assert pats[2] == r"(^|[^[:alnum:]])c\+\+ \(dev\)"
    assert len(pats) == 3
    assert lead_watch.pg_regex_escape("a.b*c") == r"a\.b\*c"


def test_new_matches_without_keywords_is_empty():
    assert run(lead_watch.new_matches(FakeConn(), {"id": 1, "keywords": []}, FRI)) == []


def test_follow_up_draft_none_without_matches():
    assert lead_watch.follow_up_draft({"email": "a@b.mk"}, []) is None


# ---------------------------------------------------------------------------
# Signed links
# ---------------------------------------------------------------------------
def test_sign_and_verify_expiry(monkeypatch):
    now = datetime(2026, 10, 16, 4, 30, tzinfo=timezone.utc)
    link = ops_copy.ops_done_link("job:abc:paycheck", now=now)
    assert "/api/ops/sent?k=job%3Aabc%3Apaycheck&e=" in link
    exp = int(now.timestamp()) + 3 * 86400
    sig = ops_copy.sign_key("job:abc:paycheck", exp)
    assert len(sig) == 40 and f"sig={sig}" in link
    assert ops_copy.verify_ops_sig("job:abc:paycheck", exp, sig, now=now)
    assert ops_copy.verify_ops_sig("job:abc:paycheck", str(exp), sig, now=now + timedelta(days=2))
    assert not ops_copy.verify_ops_sig("job:abc:paycheck", exp, sig, now=now + timedelta(days=3, seconds=1))
    assert not ops_copy.verify_ops_sig("job:abc:invoice", exp, sig, now=now)
    assert not ops_copy.verify_ops_sig("job:abc:paycheck", exp + 1, sig, now=now)
    assert not ops_copy.verify_ops_sig("job:abc:paycheck", exp, "0" * 40, now=now)
    monkeypatch.setenv("SECRET_KEY", "")
    assert not ops_copy.verify_ops_sig("job:abc:paycheck", exp, sig, now=now)


def test_small_helpers():
    assert ops_copy.key_part("17400/2026") == "17400-2026"
    assert ops_copy.iso_week(date(2026, 10, 16)) == "2026-w42"
    assert ops_copy.week_start(FRI) == MON
    assert ops_copy.fmt_date(date(2026, 10, 22)) == "22.10.2026"
    assert ops_copy.tender_link("17400/2026") == "https://nabavkidata.com/tenders/17400-2026"
    long = "збор " * 40
    st = ops_copy.short_title(long)
    assert len(st) <= 70 and not st.endswith(" ")
    html = ops_copy.render_html("<b>x</b>\nред")
    assert "&lt;b&gt;" in html and "<br>" in html


# ---------------------------------------------------------------------------
# Shortlist validation (service level)
# ---------------------------------------------------------------------------
class ShortlistConn:
    def __init__(self, status="draft"):
        self.sid = uuid.uuid4()
        self.head = {"id": self.sid, "user_id": uuid.uuid4(), "week_start": MON, "status": status,
                     "subject": "S", "intro_text": "I", "built_at": None, "sent_at": None,
                     "sent_message_id": None, "email": "k@f.mk", "full_name": None,
                     "company_name": "Ф", "account_type": "managed_client"}
        self.items = [dict(tender(f"{n}/2026", days=10), shortlist_id=self.sid, rank=n, reason="r",
                           picked=False, note=None) for n in range(1, 7)]
        self.items[5]["closing_date"] = FRI - timedelta(days=1)

    async def fetchrow(self, sql, *a):
        assert _norm(sql) == _norm(client_shortlist.SQL_GET_ONE)
        return self.head

    async def fetch(self, sql, *a):
        assert _norm(sql) == _norm(client_shortlist.SQL_ITEMS)
        return self.items

    async def execute(self, sql, *a):
        n = _norm(sql)
        if n == _norm(client_shortlist.SQL_UPDATE_HEAD):
            return "UPDATE 1" if self.head["status"] == "draft" else "UPDATE 0"
        if n == _norm(client_shortlist.SQL_SET_PICKED):
            for i in self.items:
                i["picked"] = i["tender_id"] in a[1]
        return "UPDATE 1"


def test_shortlist_pick_validation():
    c = ShortlistConn()
    with pytest.raises(ValueError):
        run(client_shortlist.update_shortlist(c, c.sid, FRI, picked=["1/2026", "2/2026", "3/2026",
                                                                     "4/2026", "5/2026"]))
    with pytest.raises(ValueError):
        run(client_shortlist.update_shortlist(c, c.sid, FRI, picked=["6/2026"]))     # closed
    with pytest.raises(ValueError):
        run(client_shortlist.update_shortlist(c, c.sid, FRI, picked=["99/2026"]))    # foreign
    out = run(client_shortlist.update_shortlist(c, c.sid, FRI, picked=["1/2026", "2/2026"]))
    assert sum(i["picked"] for i in out["items"]) == 2
    assert [i["open"] for i in out["items"]][-1] is False
    c2 = ShortlistConn(status="sent")
    with pytest.raises(client_shortlist.ShortlistStateError):
        run(client_shortlist.update_shortlist(c2, c2.sid, FRI, picked=["1/2026"]))


def test_module_import_direction():
    import inspect
    src = inspect.getsource(lead_watch)
    assert "ops_focus" not in src.replace("Must not import services.ops_focus", "").replace(
        "ops_focus imports this module", "")


# ---------------------------------------------------------------------------
# Review fixes (16 Oct 2026)
# ---------------------------------------------------------------------------
def test_short_title_ellipsis_no_dangling_word_and_sentence_case():
    t = ("ДОГОВОР ЗА ОДРЖУВАЊЕ НА ИНФОРМАЦИСКИОТ СИСТЕМ ЗА СУБВЕНЦИИ ЗА ЕЛЕКТРОНСКО "
         "ПОДНЕСУВАЊЕ НА БАРАЊА")
    st = ops_copy.short_title(t)
    assert st.endswith("…") and len(st) <= 70
    assert st.startswith("Договор за одржување")
    assert st.rstrip("…").split(" ")[-1] not in ("на", "за", "и", "во", "од", "со")
    assert ops_copy.short_title("Нешто кратко") == "Нешто кратко"
    assert ops_copy.display_title("ЈЗУ") == "ЈЗУ"                   # short acronyms untouched


def test_hot_client_draft_names_the_real_button_and_autostart_link():
    d = hot_signal.signal_draft(hot_row(acct="managed_client"))
    assert "„Започни понуда“" in d["body_text"] and "Подготви понуда" not in d["body_text"]
    assert "/tenders/17400-2026?ponuda=1&start=1" in d["body_text"]
    p = hot_signal.signal_draft(hot_row())
    assert "?ponuda=1" not in p["body_text"]


def test_goback_mentions_company_when_no_person():
    w = {"id": uuid.uuid4(), "email": "x@y.mk", "person_name": None, "company_name": "Градба ДОО",
         "source": "prospect"}
    d = lead_watch.follow_up_draft(w, [dict(tender(), hit_keywords=["софтвер"])])
    assert d["body_text"].startswith("Добар ден,\n")
    assert "целата понуда за Градба ДОО:" in d["body_text"]


def _job(status, days, **kw):
    t = tender(days=days)
    j = dict(t, id=uuid.uuid4(), user_id=uuid.uuid4(), email="klient@firma.mk", status=status,
             full_name="Ана Стојанова", company_name="Фирма ДООЕЛ", reopen_count=0, published_at=None,
             paid_at=None, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
             invoice_requested_at=None, invoice_issued_at=None, stripe_checkout_session_id=None,
             t_exists=True)
    j.update(kw)
    return j


def test_job_drafts_only_for_open_existing_tenders():
    now = datetime.now(timezone.utc)
    ok = ops_focus.classify_job(_job("approved", 2), FRI, now)
    assert [i["kind"] for i in ok] == ["job_approved_deadline"] and ok[0]["draft"]
    cancelled = ops_focus.classify_job(_job("approved", 2, t_status="cancelled"), FRI, now)
    assert [i["kind"] for i in cancelled] == ["job_approved_deadline"]
    assert cancelled[0]["draft"] is None and cancelled[0]["email"] is None
    assert "затворен/поништен" in cancelled[0]["detail"]
    missing = ops_focus.classify_job(
        _job("payment_required", 5, t_exists=False, title=None, procuring_entity=None, closing_date=None,
             invoice_issued_at=now - timedelta(days=3), invoice_number="7/2026"), FRI, now)
    assert [i["kind"] for i in missing] == ["job_payment_check"] and missing[0]["draft"] is None


def test_ready_job_close_to_deadline_is_a_client_item_with_review_draft():
    now = datetime.now(timezone.utc)
    items = ops_focus.classify_job(_job("ready", 3), FRI, now)
    assert [i["kind"] for i in items] == ["job_ready_deadline"]
    it = items[0]
    assert it["key"].endswith(":ready-deadline") and it["group"] == "clients"
    assert "/portal/bid/" in it["draft"]["body_text"] and "„Одобри сè“" in it["draft"]["body_text"]
    assert ops_focus.kind_of_key(it["key"]) == "job_ready_deadline"
    assert "job_ready_deadline" in ops_focus.OFF_DAY_KINDS
    assert ops_focus.classify_job(_job("ready", 10), FRI, now) == []


def test_caps_apply_after_done_and_snooze():
    c = FakeConn()
    rows = [hot_row(email=f"u{i}@firma.mk", tid=f"{i}/2026") for i in range(15)]
    c.hot = rows
    res = run(ops_focus.build_focus(c, FRI, manual=[]))
    hot = [i for i in res["items"] if i["kind"] == "hot_signal"]
    assert len(hot) == 10
    for it in hot[:3]:
        c.state[it["key"]] = {"kind": "hot_signal", "status": "snoozed", "done_at": None,
                              "done_via": None, "snoozed_until": FRI + timedelta(days=3),
                              "title_snapshot": None}
    res2 = run(ops_focus.build_focus(c, FRI, manual=[]))
    hot2 = [i["key"] for i in res2["items"] if i["kind"] == "hot_signal"]
    assert len(hot2) == 10 and not set(hot2) & {i["key"] for i in hot[:3]}


def _watch(i, **kw):
    w = {"id": uuid.uuid4(), "email": f"w{i}@firma.mk", "person_name": None, "company_name": f"Фирма {i}",
         "source": "lead", "keywords": ["софтвер"], "touch_count": 0, "user_id": None,
         "anchor_at": datetime.now(timezone.utc) - timedelta(days=4), "last_touched_at": None,
         "min_days_to_close": 5, "min_value_mkd": None, "max_value_mkd": None, "active": True,
         "replied_at": None}
    w.update(kw)
    return w


def test_snoozed_gobacks_do_not_hide_other_due_ones():
    lead_watch.clear_match_cache()
    c = FakeConn()
    c.watches = [_watch(i) for i in range(6)]
    for w in c.watches:
        c.matches[w["id"]] = [dict(tender(), hits=[lead_watch.keyword_pattern("софтвер")])]
    first = [i["key"] for i in run(ops_focus.build_focus(c, FRI, manual=[]))["items"] if i["kind"] == "goback"]
    assert len(first) == 4
    for k in first:
        c.state[k] = {"kind": "goback", "status": "snoozed", "done_at": None, "done_via": None,
                      "snoozed_until": FRI + timedelta(days=5), "title_snapshot": None}
    second = [i["key"] for i in run(ops_focus.build_focus(c, FRI, manual=[]))["items"] if i["kind"] == "goback"]
    assert len(second) == 2 and not set(second) & set(first)


def test_watch_without_keywords_is_reported():
    c = FakeConn()
    c.watches = [_watch(0, keywords=[]), _watch(1, keywords=[])]
    res = run(ops_focus.build_focus(c, FRI, manual=[]))
    assert any("без клучни зборови" in n and n.startswith("2 ") for n in res["notes"])


def test_send_to_one_kind_resolves_the_other_kinds_for_that_person():
    """Hot signal sent -> the same person's 'new' lead becomes contacted and their
    go-back cadence restarts, so tomorrow nobody writes to them again."""
    lead_watch.clear_match_cache()
    c = FakeConn()
    email = "info@gradba.mk"
    lead = lead_row(email=email)
    c.leads = [lead]
    c.hot = [hot_row(email=email)]
    w = _watch(0, email=email)
    c.watches = [w]
    c.matches[w["id"]] = [dict(tender("17405/2026", 20), hits=[lead_watch.keyword_pattern("софтвер")])]
    res = run(ops_focus.build_focus(c, FRI, manual=[]))
    mine = [i for i in res["items"] if i["email"] == email]
    assert [i["kind"] for i in mine] == ["hot_signal"]
    assert len(mine[0]["meta"]["collapsed_keys"]) == 2
    run(ops_focus.mark_done(c, mine[0]["key"], FRI, "send", item=mine[0]))
    assert lead["status"] == "contacted" and c.leads == []
    assert w["touch_count"] == 1                        # cadence restarted from this send


def test_ui_done_on_lead_marks_contacted_and_sent_manually_records_send():
    c = FakeConn()
    a, b = lead_row(email="a@firma.mk"), lead_row(email="b@firma.mk")
    c.leads = [a, b]
    run(ops_focus.mark_done(c, f"lead:{a['id']}", FRI, "ui"))
    assert a["status"] == "contacted" and c.sent == []
    run(ops_focus.mark_done(c, f"lead:{b['id']}", FRI, "ui", sent_manually=True))
    assert b["status"] == "contacted"
    assert [(x["to_email"], x["channel"]) for x in c.sent] == [("b@firma.mk", "manual")]
    # a second confirmation (link after UI) applies nothing twice
    run(ops_focus.mark_done(c, f"lead:{b['id']}", FRI, "link"))
    assert len(c.sent) == 1


def test_get_item_only_queries_its_own_source():
    class Strict(FakeConn):
        async def fetch(self, sql, *a):
            n = _norm(sql)
            assert n not in (_norm(ops_focus.SQL_LEADS), _norm(ops_focus.SQL_WINS),
                             _norm(lead_watch.SQL_DUE), _norm(ops_focus.SQL_CLIENT_MESSAGES)), n[:60]
            return await super().fetch(sql, *a)
    c = Strict()
    c.hot = [hot_row()]
    key = f"hot:{c.hot[0]['user_id']}:17400-2026"
    assert run(ops_focus.get_item(c, key, FRI))["key"] == key
    lead_watch.clear_match_cache()
    w = _watch(0)
    c.watches = [w]
    c.matches[w["id"]] = [dict(tender(), hits=[lead_watch.keyword_pattern("софтвер")])]
    assert run(ops_focus.get_item(c, f"goback:{w['id']}:0", FRI))["kind"] == "goback"
    assert run(ops_focus.get_item(c, f"goback:{w['id']}:1", FRI)) is None   # stale touch count
