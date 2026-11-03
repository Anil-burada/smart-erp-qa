# Smart ERP QA 6.3.0 dashboard integration of your supplied PI -> LPO -> GRN script.
# Edit THIS file in VS Code, save it, then Review & Run in Script Workspace.
# Preserved ERP locators, business formulas, and role order. No live ERP verification.
# Changes: managed-session option, local .env secrets, structured reports,
# enabled failure evidence, isolated per-run outputs, and nonzero failure exit.
# Dashboard Stop terminates the process; it does NOT undo saved ERP transactions.

# ============================================================
# FULL ERP PLAYWRIGHT AUTOMATION - GRN OK / SAVE / SUBMIT FIXED
# ============================================================
# Existing PI -> PI approvals -> LPO -> LPO approvals -> GRN
# workflow retained from user-provided source.
#
# GRN fix details:
# - grn_modal_ok(): case-insensitive lowercase / uppercase OK
# - select exact OK of Warehouse Details, then GRN Item Details
# - confirm each editor closes before continuing
# - grn_exact_visible_button(): case-insensitive SAVE / SUBMIT
# - find_new_grn(): identify exact newly saved GRN before SUBMIT
# - don't rely on volatile jssNNNN / css-XXXX button classes
#
# Copy this entire file into VS Code; don't paste old patches too.
# Run from Smart ERP Script Workspace after reviewing the saved revision.
# Browser interactions are NOT verified against your ERP login.
# Test in an authorized non-production environment first.
# ============================================================

# FULL SINGLE-FILE ERP AUTOMATION (PI -> LPO -> GRN)
# Based on your attached script and captured GRN locator JSON.
# Playwright interactions are not live-verified; use a test ERP.



SMART_ERP_SUPPORTS_EXISTING_SESSION = True
SMART_ERP_REQUIRED_CREDENTIALS = []  # This script handles its own login values.

import json
from backend.script_runtime import stage, check, emit, run_directory, open_script_browser, capture_failure
import os
import signal
import subprocess
import sys

import random

import re

import time

import traceback



from datetime import datetime, timezone, timedelta

from decimal import Decimal, ROUND_HALF_UP


from pathlib import Path



from playwright.sync_api import (

    sync_playwright,

    expect,

    TimeoutError as PWTimeout

)





# ============================================================

# CONFIGURATION

# ============================================================



ERP_URL = os.environ.get("ERP_URL", "https://ba.kagamierp.com/leocem")



TIMEOUT = 30000

TOTAL_RECORDS = 1




TAX_RATE = Decimal("15")

TOLERANCE = Decimal("0.001")

EXPECTED_CHARGES = Decimal("0.00")



BASE = Path(__file__).resolve().parent



COUNTER_FILE = BASE / "dropdown_counters.json"

PO_FILE = BASE / "exact_po_sequence.json"

SCREENSHOTS = (run_directory() or BASE) / "evidence"



TEST_DATA = [

    {

        "name": "Record 1",

        "qty": 12,

        "narration": "Automation Material Alpha"

    },

    {

        "name": "Record 2",

        "qty": 27,

        "narration": "Automation Material Beta"

    },

    {

        "name": "Record 3",

        "qty": 43,

        "narration": "Automation Material Gamma"

    }

]



PI_REGEX = re.compile(

    r"^PI/[A-Za-z0-9_-]+/\d{4}/\d+$"

)



AMOUNT_REGEX = re.compile(
    r"^\(?-?(?:₹|\$)?\s*[\d,]+(?:\.\d+)?\)?$"
)





# ============================================================

# GENERAL HELPERS

# ============================================================



def log(title):

    print(

        "\n" + "=" * 60 +

        "\n" + title +

        "\n" + "=" * 60

    )





def norm(value):

    return " ".join(

        str(value).replace("\u00a0", " ").split()

    ).casefold()





def money(value):

    return Decimal(str(value)).quantize(

        Decimal("0.01"),

        rounding=ROUND_HALF_UP

    )





def decimal(value):



    s = str(value).strip()



    s = s.replace(",", "")

    s = s.replace("₹", "")

    s = s.replace("$", "")



    if s.startswith("(") and s.endswith(")"):

        s = "-" + s[1:-1]



    return Decimal(s.strip())





def read_json(path, default):



    if path.exists():

        return json.loads(

            path.read_text(encoding="utf-8")

        )



    return default





def write_json(path, value):



    temp = path.with_suffix(".tmp")



    temp.write_text(

        json.dumps(value, indent=2),

        encoding="utf-8"

    )



    temp.replace(path)





counters = read_json(COUNTER_FILE, {})





# ============================================================

# GREEN / RED CALCULATION HIGHLIGHTING

# ============================================================



def mark_calculation(

    locator,

    passed,

    expected=None,

    actual=None,

    difference=None

):



    try:



        locator.evaluate(

            """

            (el, details) => {



                const {

                    passed,

                    expected,

                    actual,

                    difference

                } = details;



                const color = passed

                    ? '#16803c'

                    : '#c41e3a';



                const background = passed

                    ? 'rgba(34,197,94,0.14)'

                    : 'rgba(239,68,68,0.16)';



                el.style.setProperty(

                    'outline',

                    `3px solid ${color}`,

                    'important'

                );



                el.style.setProperty(

                    'outline-offset',

                    '-2px',

                    'important'

                );



                el.style.setProperty(

                    'background-color',

                    background,

                    'important'

                );



                el.style.setProperty(

                    'border-radius',

                    '4px',

                    'important'

                );



                el.setAttribute(

                    'data-qa-validation',

                    passed ? 'PASS' : 'FAIL'

                );



                let note = el.querySelector(

                    ':scope > .qa-calculation-note'

                );



                if (!note) {

                    note = document.createElement('div');

                    note.className = 'qa-calculation-note';

                    el.appendChild(note);

                }



                note.style.cssText = [

                    'display:block',

                    'font-size:11px',

                    'font-weight:700',

                    `color:${color}`,

                    'padding:3px 5px',

                    'line-height:1.5',

                    'white-space:normal'

                ].join(';');



                if (expected === null) {



                    note.textContent =

                        'FAIL - Could not read ERP amount';



                } else {



                    note.textContent =

                        `${passed ? 'PASS' : 'FAIL'}`

                        + ` | Expected: ${expected}`

                        + ` | Actual: ${actual}`

                        + ` | Difference: ${difference}`;

                }

            }

            """,

            {

                "passed": passed,

                "expected": (

                    None if expected is None

                    else str(expected)

                ),

                "actual": (

                    None if actual is None

                    else str(actual)

                ),

                "difference": (

                    None if difference is None

                    else str(difference)

                )

            }

        )



    except Exception as error:

        print(

            "Could not highlight calculation field:",

            error

        )





def mark_error(locator):

    mark_calculation(locator, False)





# ============================================================

# SCREENSHOT ON FAILURE

# ============================================================



def screenshot_failure(page, stage, messages):



    log(stage + " FAILED - NO LPO SAVE")



    for msg in messages:

        print(msg)



    try:



        SCREENSHOTS.mkdir(

            parents=True,

            exist_ok=True

        )



        path = SCREENSHOTS / (

            f"{stage}_"

            f"{datetime.now():%Y%m%d_%H%M%S_%f}.png"

        )



        page.evaluate(

            """

            messages => {



                document.getElementById(

                    'qa-failure'

                )?.remove();



                const x = document.createElement('pre');



                x.id = 'qa-failure';



                x.style.cssText = `

                    position:fixed;

                    top:8px;

                    left:8px;

                    right:8px;

                    z-index:2147483647;

                    background:#fff0f0;

                    color:#9a0000;

                    border:3px solid red;

                    padding:12px;

                    white-space:pre-wrap;

                    max-height:35vh;

                    overflow:auto;

                `;



                x.textContent =

                    'AUTOMATION FAILURE\\\n'

                    + messages.join('\\\n');



                document.body.appendChild(x);

            }

            """,

            messages

        )



        page.screenshot(

            path=str(path),

            full_page=True

        )



        print("Screenshot:", path)



    except Exception as error:

        print(

            "Could not capture screenshot:",

            error

        )





# ============================================================

# ERP LOGIN

# ============================================================



def login(page, username):
    """Use a locally configured authorized test-account password."""
    allowed_users = {"DMG0041", "DMG0013", "DMG0051", "DMG0052"}
    if username not in allowed_users:
        raise ValueError(f"Unexpected ERP account: {username}")

    log(f"ERP LOGIN - {username}")
    username_input = page.locator("#username")
    password_input = page.locator("#password")
    expect(username_input).to_be_visible(timeout=TIMEOUT)
    username_input.fill(username)
    # Preserves the supplied login behavior: password uses the username.
    # Edit this login function in VS Code if your test accounts use other passwords.
    password_input.fill(username)
    page.get_by_role("link", name="LOGIN", exact=True).click()

    try:
        page.locator("div.pro-sidebar").wait_for(
            state="visible", timeout=TIMEOUT
        )
    except PWTimeout:
        raise RuntimeError(f"Could not confirm login for {username}")
    print(f"PASS: logged in as {username}")


def logout(page, username):
    """Click the supplied LogoutIcon's enclosing button and verify login screen."""
    log(f"LOGOUT - {username}")
    icon = page.locator('svg[data-testid="LogoutIcon"]:visible')
    expect(icon).to_have_count(1, timeout=TIMEOUT)
    button = icon.locator("xpath=ancestor::button[1]")
    if button.count() == 1:
        button.click()
    else:
        # Some layouts attach the click handler to a wrapping element.
        icon.click()

    # Some ERPs show a confirmation modal after clicking logout.
    confirm = page.get_by_role(
        "button", name=re.compile(r"^(Yes|Confirm|Logout|Log out)$", re.I)
    ).and_(page.locator(":visible"))
    if confirm.count() == 1 and page.locator("#username").is_hidden():
        confirm.click()

    try:
        page.locator("#username").wait_for(state="visible", timeout=TIMEOUT)
    except PWTimeout:
        raise RuntimeError(
            f"Logout could not be confirmed for {username}; "
            "refusing to log in as another user in the same session"
        )
    print(f"PASS: logged out {username}")


def global_search(page, query, expected):
    """Navigate using ERP Global Search even when results rerender or omit spaces.

    For example, PurchaseIndent Approval and Purchase Indent Approval are
    considered equivalent, but the target still must be unambiguous.
    """
    log("GLOBAL SEARCH: " + query)

    search = page.get_by_placeholder("Where Do You Want To Go..?", exact=True)
    if not search.is_visible():
        page.keyboard.press("Control+Space")
    search.wait_for(state="visible", timeout=TIMEOUT)
    search.fill(query)

    # Compare full labels, ignoring case, spacing and punctuation.
    # Do not enumerate live Playwright locators by nth(i): result indexes change.
    target_key = re.sub(r"[^a-z0-9]", "", expected.casefold())
    deadline = time.monotonic() + 30
    last_diagnostic = []
    refreshed = False

    while time.monotonic() < deadline:
        # An in-page, single-pass DOM snapshot avoids stale .nth(index) locators.
        # Only look at candidate search-result elements (not page-wide divs).
        outcome = page.evaluate(
            """target => {
                const key = text => (text || '').toLowerCase()
                    .replace(/[^a-z0-9]/g, '');
                const visible = el => {
                    const r = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return r.width > 0 && r.height > 0 &&
                        style.visibility !== 'hidden' && style.display !== 'none';
                };
                const selectors = '[role="option"], [role="menuitem"], li, a';
                const nodes = Array.from(document.querySelectorAll(selectors))
                    .filter(visible);
                const exact = nodes.filter(el => key(el.innerText) === target);
                // Equivalent nested candidates are one result, not duplicates.
                const leaves = exact.filter(el =>
                    !exact.some(other => other !== el && el.contains(other))
                );
                const samples = nodes.map(el => (el.innerText || '').trim())
                    .filter(text => /approval|indent|lpo/i.test(text))
                    .slice(0, 12);
                if (leaves.length === 1) {
                    leaves[0].click();
                    return {clicked: true, samples};
                }
                return {clicked: false, matches: leaves.length, samples};
            }""",
            target_key,
        )
        last_diagnostic = outcome.get("samples", [])
        if outcome.get("clicked"):
            print("Global Search opened:", expected)
            return

        # Fallback when search results are rendered in plain text containers.
        # Accept 'PurchaseIndent Approval' AND 'Purchase Indent Approval'.
        words = expected.split()
        flexible_pattern = re.compile(
            r"^\s*" + r"\s*".join(map(re.escape, words)) + r"\s*$",
            re.I,
        )
        fallback = page.get_by_text(flexible_pattern).and_(page.locator(":visible"))
        if fallback.count() == 1:
            try:
                fallback.click(timeout=1000)
                print("Global Search opened:", expected)
                return
            except PWTimeout:
                pass

        # If the initial query returns no results, try the human-spaced title.
        if not refreshed and time.monotonic() > deadline - 19:
            search.fill(expected)
            refreshed = True
            print("Global Search retry using:", expected)

        page.wait_for_timeout(250)

    raise RuntimeError(
        f"Global Search could not find a unique clickable result for "
        f"{expected!r}; query={query!r}; "
        f"visible candidate labels={last_diagnostic!r}; url={page.url}"
    )



def dropdown_options(page, field):



    lid = field.get_attribute(

        "aria-controls"

    )



    if lid:



        scoped = page.locator(

            f'[id="{lid}"] '

            '[role="option"]:visible'

        )



        if scoped.count():

            return scoped



    return page.locator(

        '[role="option"]:visible'

    )





def open_dropdown(page, field):



    expect(field).to_be_visible(

        timeout=TIMEOUT

    )



    field.scroll_into_view_if_needed()



    button = field.locator(

        "xpath=.."

    ).locator(

        'button[aria-label="Open"]'

    )



    if (

        button.count() == 1

        and button.is_visible()

    ):



        button.click()



    else:

        field.click()





def options_as_text(page, field):



    opts = dropdown_options(

        page,

        field

    )



    values = []

    seen = set()



    for i in range(opts.count()):



        el = opts.nth(i)



        if not el.is_enabled():

            continue



        value = el.inner_text().strip()



        if (

            value

            and norm(value) not in seen

        ):



            values.append(value)

            seen.add(norm(value))



    return values





def select_option(page, field, target):



    for attempt in range(4):



        opts = dropdown_options(

            page,

            field

        )



        matches = [

            opts.nth(i)

            for i in range(opts.count())

            if (

                opts.nth(i).is_enabled()

                and norm(

                    opts.nth(i).inner_text()

                ) == norm(target)

            )

        ]



        if len(matches) > 1:



            raise RuntimeError(

                "Ambiguous dropdown option: "

                + target

            )



        if len(matches) == 1:



            try:



                matches[0].click(

                    timeout=4000

                )



                pattern = re.compile(

                    r"^\s*"

                    + r"\s+".join(

                        map(

                            re.escape,

                            target.split()

                        )

                    )

                    + r"\s*$",

                    re.I

                )



                expect(field).to_have_value(

                    pattern,

                    timeout=5000

                )



                print("Selected:", target)

                return target



            except (PWTimeout, AssertionError):

                pass



        open_dropdown(page, field)



        if (

            attempt >= 1

            and field.get_attribute("role")

            == "combobox"

            and field.get_attribute("readonly")

            is None

        ):

            field.fill(target)



        page.wait_for_timeout(400)



    raise RuntimeError(

        f"Cannot select '{target}'; "

        f"currently visible: "

        f"{options_as_text(page, field)[:30]}"

    )





# ============================================================

# SELECT EXACT DROPDOWN VALUE

# ============================================================



def select_exact(page, field, target):



    open_dropdown(page, field)



    end = time.monotonic() + 12



    values = []



    while time.monotonic() < end:



        values = options_as_text(

            page,

            field

        )



        if values:

            break



        page.wait_for_timeout(250)



    matches = [

        x

        for x in values

        if norm(x) == norm(target)

    ]



    if len(matches) != 1:



        raise RuntimeError(

            f"Required option {target!r} "

            f"not present; available: {values}"

        )



    return select_option(

        page,

        field,

        matches[0]

    )





# ============================================================

# ROUND-ROBIN DROPDOWN

# ============================================================



def round_robin(page, field_id):



    log("ROUND ROBIN: " + field_id)



    field = page.locator(

        f'[id="{field_id}"]'

    )



    open_dropdown(page, field)



    end = time.monotonic() + 12



    values = []



    while time.monotonic() < end:



        values = options_as_text(

            page,

            field

        )



        if values:

            break



        page.wait_for_timeout(300)



    if not values:



        raise RuntimeError(

            "No options for " + field_id

        )



    old = counters.get(field_id, 0)



    target = values[

        old % len(values)

    ]



    selected = select_option(

        page,

        field,

        target

    )



    counters[field_id] = old + 1



    write_json(

        COUNTER_FILE,

        counters

    )



    return selected





# ============================================================

# PURCHASE INDENT ITEM SELECTION

# ============================================================



def select_pi_item(page):



    return round_robin(

        page,

        "PurchaseIndentItemDetails_92.itemId"

    )





# ============================================================

# REQUIRED DATE - TIMEZONE ERROR FIXED

# ============================================================



def select_required_date(page):



    # IMPORTANT:

    # India Standard Time is UTC+05:30.

    # Does not require ZoneInfo or tzdata.

    today = datetime.now(

        timezone(timedelta(hours=5, minutes=30))

    )



    target = today.strftime("%d/%m/%Y")



    print("Today's Required Date (IST):", target)



    labels = page.locator(

        "span.MuiFormLabel-root:visible"

    ).filter(

        has_text=re.compile(

            r"^\s*Required Date\s*\*?\s*$",

            re.I

        )

    )



    field = labels.locator(

        "xpath=.."

    ).locator(

        'input[placeholder="dd/mm/yyyy"]:visible'

    )



    expect(field).to_have_count(1)



    if field.input_value() == target:

        return target



    field.click()



    calendar = page.locator(

        ".MuiCalendarPicker-root:visible, "

        ".MuiDateCalendar-root:visible"

    )



    try:



        calendar.wait_for(

            state="visible",

            timeout=3000

        )



    except PWTimeout:



        wrapper = field.locator(

            'xpath=ancestor::div['

            'contains(@class,"MuiInputBase-root")][1]'

        )



        wrapper.locator(

            'svg[data-testid="CalendarMonthOutlinedIcon"],'

            'svg[data-testid="CalendarMonthIcon"],'

            'svg[data-testid="CalendarTodayIcon"],'

            'svg[data-testid="CalendarIcon"]'

        ).first.click()



        calendar.wait_for(

            state="visible",

            timeout=TIMEOUT

        )



    header = calendar.locator(

        ".MuiPickersCalendarHeader-label"

    )



    for _ in range(24):



        shown_text = header.inner_text().strip()



        if shown_text == today.strftime("%B %Y"):

            break



        shown = datetime.strptime(

            shown_text,

            "%B %Y"

        )



        direction = (

            "Next month"

            if (shown.year, shown.month)

            < (today.year, today.month)

            else "Previous month"

        )



        calendar.get_by_role(

            "button",

            name=direction,

            exact=True

        ).click()



        expect(header).not_to_have_text(

            shown_text

        )



    else:



        raise RuntimeError(

            "Could not reach current calendar month"

        )



    day = calendar.locator(

        'button[role="gridcell"]:not('

        '.MuiPickersDay-dayOutsideMonth)'

    ).filter(

        has_text=re.compile(

            rf"^{today.day}$"

        )

    )



    expect(day).to_have_count(1)



    day.click()



    expect(field).to_have_value(target)



    print("Required Date selected:", target)



    return target





# ============================================================

# AG GRID HELPERS

# ============================================================



def grid_rows(page):



    rows = page.locator(

        ".ag-center-cols-container .ag-row"

    )



    return [

        {

            "index": rows.nth(i).get_attribute(

                "row-index"

            ),

            "text": rows.nth(i).inner_text().strip()

        }

        for i in range(rows.count())

        if rows.nth(i).get_attribute("row-index")

        is not None

    ]





def grid_transaction_row(page, number):



    rows = page.locator(

        ".ag-center-cols-container .ag-row"

    )



    matches = []



    for i in range(rows.count()):



        row = rows.nth(i)



        values = [

            v.strip()

            for v in row.locator(

                ".ag-cell"

            ).all_inner_texts()

        ]



        if number in values:



            matches.append(

                row.get_attribute("row-index")

            )



    if len(matches) != 1:



        raise RuntimeError(

            f"Expected one grid row for {number}; "

            f"found {len(matches)}"

        )



    return matches[0]





def select_grid_row(page, index):
    """Select only the matched AG Grid row; never use changing ag-### IDs."""
    for column in ("ag-pinned-left-cols-container", "ag-center-cols-container"):
        row = page.locator(f'.{column} .ag-row[row-index="{index}"]')
        if row.count() != 1:
            continue
        # Typical AG Grid markup: input.ag-checkbox-input[id="ag-832-input"].
        # The numeric id changes every render; the row-index comes from the
        # exact transaction number match performed by grid_transaction_row.
        checkbox = row.locator('input.ag-checkbox-input[type="checkbox"]')
        if checkbox.count() == 1:
            if not checkbox.is_checked():
                try:
                    checkbox.check(timeout=3000)
                except PWTimeout:
                    wrapper = row.locator('.ag-checkbox-input-wrapper').first
                    if wrapper.count() == 0:
                        raise
                    wrapper.click(timeout=TIMEOUT)
            expect(checkbox).to_be_checked(timeout=TIMEOUT)
            print(f"Selected AG Grid row-index={index}")
            return
        wrapper = row.locator('.ag-checkbox-input-wrapper')
        if wrapper.count() == 1:
            if not wrapper.evaluate("el => el.classList.contains('ag-checked')"):
                wrapper.click(timeout=TIMEOUT)
            if not wrapper.evaluate("el => el.classList.contains('ag-checked')"):
                raise RuntimeError(f"Checkbox not selected for row {index}")
            print(f"Selected AG Grid row-index={index}")
            return
    raise RuntimeError(f"Could not locate checkbox for AG Grid row {index}")


# ============================================================

# PURCHASE INDENT QUANTITY VALIDATION

# ============================================================




def validate_pi_quantity(value):
    """The same numeric guard used by the live PI item entry."""
    amount = decimal(value)
    if amount <= 0:
        raise ValueError("Indent Quantity must be greater than zero")
    return amount


def smart_erp_run_negative_scenarios():
    """Non-destructive negative checks of the actual PI quantity guard.

    These do NOT enter invalid values in the Leocem browser or prove that
    live ERP validation rejects them. They are labeled Local negative rules.
    """
    samples = [('Zero indent quantity', 0),
               ('Negative indent quantity', -5),
               ('Alphabetic indent quantity', 'invalid-quantity'),
               ('Mixed numeric indent quantity', '12abc')]
    failures = 0
    for name, invalid in samples:
        try:
            validate_pi_quantity(invalid)
        except (ValueError, ArithmeticError):
            check('Negative / Local PI rule: ' + name, True,
                  'Reject invalid quantity before ERP submission',
                  'Rejected ' + repr(invalid) + ' by the saved script quantity guard',
                  process='Local script validation (no ERP browser)', category='Negative')
        else:
            failures += 1
            check('Negative / Local PI rule: ' + name, False,
                  'Reject invalid quantity before ERP submission',
                  'Unexpectedly accepted ' + repr(invalid),
                  process='Local script validation (no ERP browser)', category='Negative')
    if failures:
        raise AssertionError(str(failures) + ' local negative quantity rule(s) failed')


def enter_purchase_indent_quantity(

    page,

    quantity

):



    log("PURCHASE INDENT QUANTITY")



    field = page.locator(

        '[id="PurchaseIndentItemDetails_92.indentQty"]'

    )



    expect(field).to_be_visible(

        timeout=TIMEOUT

    )



    expect(field).to_be_enabled(

        timeout=TIMEOUT

    )



    target = validate_pi_quantity(quantity)



    for attempt in range(1, 5):



        field.click(timeout=TIMEOUT)



        field.fill(

            str(quantity),

            timeout=TIMEOUT

        )



        page.wait_for_timeout(350)



        field.press("Tab")



        page.wait_for_timeout(650)



        shown = field.input_value().strip()



        print(

            f"Indent Qty attempt {attempt}/4: "

            f"expected={target}, "

            f"actual={shown!r}"

        )



        try:

            valid = decimal(shown) == target

        except Exception:

            valid = False



        if valid:



            page.wait_for_timeout(450)



            try:



                if decimal(

                    field.input_value()

                ) == target:



                    print(

                        "PASS: Purchase Indent "

                        "quantity retained"

                    )



                    check('Purchase Indent: Item Quantity', True, target, field.input_value(),
                          page=page, process='Purchase Indent')
                    return



            except Exception:

                pass



    check('Purchase Indent: Item Quantity', False, target, field.input_value(),
          page=page, process='Purchase Indent')
    mark_error(field)



    raise RuntimeError(

        f"Indent Quantity reset by ERP: "

        f"expected={target}, "

        f"actual={field.input_value()!r}. "

        "Item OK NOT clicked."

    )





# ============================================================

# PURCHASE INDENT ITEM OK

# ============================================================



def commit_purchase_indent_item(

    page,

    quantity

):



    field = page.locator(

        '[id="PurchaseIndentItemDetails_92.indentQty"]'

    )



    if decimal(

        field.input_value()

    ) != decimal(quantity):



        mark_error(field)



        raise RuntimeError(

            "Indent Quantity changed before Item OK; "

            "item was not submitted"

        )



    dialog = page.get_by_role(

        "dialog"

    ).filter(

        has=field

    )



    if dialog.count() == 1:



        ok = dialog.get_by_role(

            "button",

            name="ok",

            exact=True

        )



    else:



        ok = page.get_by_role(

            "button",

            name="ok",

            exact=True

        ).and_(

            page.locator(":visible")

        )



    expect(ok).to_have_count(

        1,

        timeout=TIMEOUT

    )



    expect(ok).to_be_enabled(

        timeout=TIMEOUT

    )



    ok.click(timeout=TIMEOUT)



    try:



        page.locator(

            '[id="PurchaseIndentItemDetails_92.itemId"]'

        ).wait_for(

            state="hidden",

            timeout=7000

        )



    except PWTimeout:



        shown = (

            field.input_value()

            if field.is_visible()

            else "not visible"

        )



        message = (

            "Indent item dialog remained open after OK"

        )



        warning = page.get_by_text(

            "Kindly Check Indent Quantity",

            exact=False

        )



        if (

            warning.count()

            and warning.first.is_visible()

        ):



            message += (

                ": ERP says Kindly Check Indent Quantity"

            )



        mark_error(field)



        raise RuntimeError(

            f"{message}; "

            f"expected={quantity}, "

            f"actual={shown!r}"

        )



    print(

        "PASS: Purchase Indent item editor closed"

    )





# ============================================================

# PURCHASE INDENT CREATION

# ============================================================




def capture_pi_uom(page):
    """Read UOM from the PI item editor if the ERP exposes it.

    If the field is not identifiable, it is not included in PDF checks.
    """
    candidates = page.locator(
        '[id="PurchaseIndentItemDetails_92.uomId"]:visible'
    )
    if candidates.count() == 1:
        field = candidates.first
        value = field.input_value().strip() if field.evaluate(
            'el => el.tagName === "INPUT"'
        ) else field.inner_text().strip()
        if value:
            print('Captured PI UOM:', value)
            return value
    print('PI UOM not captured; print UOM check will be skipped')
    return None

@stage('Purchase Indent: create and display', 'New PI transaction is identified and visible in its detail view', verified=True)
def create_indent(page, record):



    log("CREATE PURCHASE INDENT")



    global_search(

        page,

        "PurchaseIndent Creation",

        "PurchaseIndent Creation"

    )



    page.get_by_text(

        "Purchase Indents",

        exact=True

    ).wait_for(

        state="visible"

    )



    page.locator(

        ".ag-root:visible"

    ).first.wait_for(

        state="visible"

    )



    old = {

        r["text"]

        for r in grid_rows(page)

    }



    page.get_by_role(

        "button",

        name="CREATE",

        exact=True

    ).click()



    kind = round_robin(

        page,

        "PurchaseIndent_37.indentTypeId"

    )



    dept = round_robin(

        page,

        "PurchaseIndent_37.departmentId"

    )



    purchase = select_exact(

        page,

        page.locator(

            '[id="PurchaseIndent_37.purchaseTypeId"]'

        ),

        "Local Purchase"

    )



    section_value = round_robin(

        page,

        "PurchaseIndent_37.sectionId"

    )



    asset = round_robin(

        page,

        "PurchaseIndent_37.assetMasterId"

    )



    # Required Date using IST

    selected_date = select_required_date(page)



    page.locator(

        'textarea[name="PurchaseIndent_37.narration"]'

    ).fill(

        record["narration"]

    )



    # Add Item

    page.locator(

        'svg[data-testid="PlaylistAddOutlinedIcon"]'

    ).click()



    item = select_pi_item(page)



    # Wait until Item-dependent fields settle.

    page.wait_for_timeout(650)

    # Optional form value; never guess UOM from the item name.
    captured_uom = capture_pi_uom(page)



    enter_purchase_indent_quantity(

        page,

        record["qty"]

    )



    pi_print_snapshot = capture_pi_print_creation(page, item, record["qty"], captured_uom)

    commit_purchase_indent_item(

        page,

        record["qty"]

    )



    # Save Purchase Indent

    page.get_by_role(

        "button",

        name="Save",

        exact=True

    ).click()



    page.locator(

        '[id="PurchaseIndent_37.indentTypeId"]'

    ).wait_for(

        state="hidden"

    )



    # Find newly created transaction

    end = time.monotonic() + 30

    number = None



    while time.monotonic() < end:



        fresh = [

            r

            for r in grid_rows(page)

            if r["text"] not in old

        ]



        if len(fresh) == 1:



            row_index = fresh[0]["index"]



            row = page.locator(

                ".ag-center-cols-container "

                f'.ag-row[row-index="{row_index}"]'

            )



            found = [

                v.strip()

                for v in row.locator(

                    ".ag-cell"

                ).all_inner_texts()

                if PI_REGEX.fullmatch(v.strip())

            ]



            if len(found) == 1:



                number = found[0]

                break



        page.wait_for_timeout(800)



    if not number:



        raise RuntimeError(

            "Could not uniquely identify "

            "new PI transaction"

        )



    print("Created PI:", number)



    select_grid_row(

        page,

        grid_transaction_row(

            page,

            number

        )

    )



    # Submit Purchase Indent

    page.get_by_role(

        "button",

        name="SUBMIT",

        exact=True

    ).click()



    expect(

        page.get_by_role(

            "heading",

            name="View Purchase Indent",

            exact=True

        )

    ).to_be_visible()



    expect(

        page.locator("main")

    ).to_contain_text(number)



    return {

        "transaction": number,
        "_print_creation": pi_print_snapshot,

        "department": dept,

        "qty": record["qty"],

        "item": item,

        "uom": captured_uom,

        "kind": kind,

        "purchase": purchase,

        "section": section_value,

        "asset": asset,

        "date": selected_date

    }





# ============================================================

# PURCHASE INDENT APPROVALS

# ============================================================



@stage('Purchase Indent: approval', 'Approval control is clicked for the exact PI; final status needs an assertion', verified=False)
def approve_indent(page, number, username, from_pi_view=False):
    """Open PI Approval, select the exact PI, and click Approve once."""
    log(f"PURCHASE INDENT APPROVAL - {username} - {number}")

    if from_pi_view:
        page.get_by_role("button", name="Back", exact=True).click()

    global_search(page, "purchaseindent approval", "Purchase Indent Approval")
    page.locator(".ag-root:visible").first.wait_for(
        state="visible", timeout=TIMEOUT
    )

    end = time.monotonic() + 30
    while True:
        try:
            row_index = grid_transaction_row(page, number)
            break
        except RuntimeError:
            if time.monotonic() >= end:
                raise RuntimeError(
                    f"PI {number} unavailable for approval by {username}"
                )
            page.wait_for_timeout(700)

    select_grid_row(page, row_index)
    approve = page.get_by_role("button", name="Approve", exact=True)
    expect(approve).to_be_visible(timeout=TIMEOUT)
    expect(approve).to_be_enabled(timeout=TIMEOUT)
    approve.click()

    # Do not claim backend approval from a successful button click alone.
    print(f"Approve clicked for PI {number} by {username}; "
          "verify status/audit trail in ERP")
    page.wait_for_timeout(2000)
    return "APPROVE_CLICKED_NOT_INDEPENDENTLY_VERIFIED"


def find_department(page):



    by_role = page.get_by_role(

        "combobox",

        name=re.compile(

            r"^\s*Department\s*\*?\s*$",

            re.I

        )

    )



    if by_role.count() == 1:

        return by_role



    options = page.locator(

        'input[role="combobox"]:visible'

    )



    matches = [

        options.nth(i)

        for i in range(options.count())

        if (

            options.nth(i).get_attribute("id") or ""

        ).startswith("LocalPO_194.")

        and "department" in (

            options.nth(i).get_attribute("id") or ""

        ).lower()

    ]



    if len(matches) != 1:



        raise RuntimeError(

            "LPO Department input "

            "not uniquely identified"

        )



    return matches[0]





# ============================================================

# SELECT SAME PURCHASE INDENT

# ============================================================



def select_pi_reference(page, number):



    field = page.locator(

        '[id="LocalPO_194.purchaseIndentId"]'

    )



    open_dropdown(page, field)



    for mode in ("open", "filter"):



        if mode == "filter":

            field.fill(number)



        end = time.monotonic() + 14



        while time.monotonic() < end:



            opts = dropdown_options(

                page,

                field

            )



            matched = [

                opts.nth(i)

                for i in range(opts.count())

                if (

                    opts.nth(i).is_enabled()

                    and number.casefold()

                    in opts.nth(i).inner_text().casefold()

                )

            ]



            if len(matched) == 1:



                matched[0].click()



                expect(field).to_have_value(

                    re.compile(

                        re.escape(number),

                        re.I

                    )

                )



                page.locator(

                    'svg[data-testid="EditOutlinedIcon"]:visible'

                ).first.wait_for(

                    state="visible"

                )



                return



            if len(matched) > 1:



                raise RuntimeError(

                    "Ambiguous PI dropdown options"

                )



            page.wait_for_timeout(400)



    raise RuntimeError(

        "PI transaction not present "

        "in LPO dropdown: " + number

    )





# ============================================================

# FOUR-DIGIT PO NUMBER

# ============================================================



def po_number(page):



    number = read_json(

        PO_FILE,

        {"next_number": 1000}

    )["next_number"]



    if (

        type(number) is not int

        or not 1000 <= number <= 9999

    ):



        raise RuntimeError(

            "Four-digit PO sequence "

            "is invalid or exhausted"

        )



    write_json(

        PO_FILE,

        {"next_number": number + 1}

    )



    value = f"{number:04d}"



    field = page.locator(

        '[id="LocalPO_194.oldpono"]'

    )



    field.fill(value)

    field.press("Tab")



    expect(field).to_have_value(value)



    if field.get_attribute(

        "aria-invalid"

    ) == "true":



        raise RuntimeError(

            "ERP rejected PO number: " + value

        )



    return value





# ============================================================

# LPO NUMERIC INPUT WITH RETRIES

# ============================================================



def input_number(page, field_id, value):



    field = page.locator(

        f'[id="{field_id}"]'

    )



    expect(field).to_be_visible(

        timeout=TIMEOUT

    )



    field.scroll_into_view_if_needed()



    target = decimal(value)



    for attempt in range(1, 4):



        field.click(timeout=TIMEOUT)



        field.fill(str(value))



        field.press("Tab")



        page.wait_for_timeout(300)



        current = field.input_value().strip()



        print(

            f"{field_id}: "

            f"attempt={attempt} "

            f"expected={target} "

            f"actual={current!r}"

        )



        if current and decimal(current) == target:

            return



    mark_error(field)



    raise RuntimeError(

        f"ERP did not retain {field_id}: "

        f"expected={target}, "

        f"actual={field.input_value()!r} "

        "after 3 attempts"

    )





def verify_lpo_numeric_fields(

    page,

    qty,

    price,

    discount_pct

):



    for suffix, expected in (

        ("quantity", qty),

        ("unitprice", price),

        ("dispercent", discount_pct)

    ):



        field_id = (

            f"LocalPOdetails_195.{suffix}"

        )



        field = page.locator(

            f'[id="{field_id}"]'

        )



        expect(field).to_be_visible(

            timeout=TIMEOUT

        )



        actual = field.input_value().strip()



        if (

            not actual

            or decimal(actual) != decimal(expected)

        ):

            check('Local Purchase Order: ' + {'quantity': 'Item Quantity',
                  'unitprice': 'Unit Price', 'dispercent': 'Discount Percentage'}[suffix],
                  False, expected, actual, page=page, process='Local Purchase Order')

            mark_error(field)



            raise RuntimeError(

                f"{field_id} changed after "

                f"entering PGST/Discount: "

                f"expected={expected}, "

                f"actual={actual!r}. "

                "Save blocked."

            )



        print(

            f"PASS | {field_id} | "

            f"Expected={expected} | Actual={actual}"

        )
        check('Local Purchase Order: ' + {'quantity': 'Item Quantity',
              'unitprice': 'Unit Price', 'dispercent': 'Discount Percentage'}[suffix],
              True, expected, actual, page=page, process='Local Purchase Order')




# ============================================================

# SELECT PGST - ERP AUTOMATICALLY APPLIES 15%

# ============================================================



def select_pgst(page):



    log(

        "SELECT PGST: PREDEFINED 15% IN ERP"

    )



    field = page.locator(

        '[id="LocalPOdetails_195.taxDefinitionId"]'

    )



    return select_exact(

        page,

        field,

        "PGST"

    )





# ============================================================

# ERP CALCULATION AMOUNT LOCATORS

# ============================================================



def amount_field(container, label):



    fields = container.locator(

        "div.fieldPresentation"

    )



    matches = []



    for i in range(fields.count()):



        field = fields.nth(i)



        labels = field.locator(

            "span.MuiFormLabel-root"

        )



        if (

            labels.count() == 1

            and norm(

                labels.inner_text().replace("*", "")

            ) == norm(label)

        ):

            matches.append(field)



    if len(matches) != 1:



        raise RuntimeError(

            f"'{label}' amount container "

            f"count={len(matches)}"

        )



    return matches[0]





def read_amount(container, label):



    field = amount_field(

        container,

        label

    )



    # Avoid unstable generated CSS classes.

    inputs = field.locator(

        "input:visible"

    )



    if (

        inputs.count() == 1

        and inputs.input_value().strip()

    ):



        return decimal(

            inputs.input_value()

        )



    lines = [

        line.strip()

        for line in field.inner_text().splitlines()

        if line.strip()

    ]



    candidates = []



    for line in lines:



        if norm(

            line.replace("*", "")

        ) == norm(label):

            continue



        if AMOUNT_REGEX.fullmatch(line):

            candidates.append(decimal(line))



    if len(candidates) == 1:



        print(

            "ERP ACTUAL |",

            label,

            "=",

            candidates[0]

        )



        return candidates[0]



    print(

        "READ ERROR HTML:",

        field.evaluate(

            "el => el.outerHTML"

        )

    )



    raise RuntimeError(

        f"Could not read a unique number "

        f"for {label}: {candidates}; "

        f"text={lines}"

    )





# ============================================================

# EXPECTED VS ACTUAL COMPARISON

# ============================================================



def compare(

    container,

    label,

    expected,

    errors,

    prefix="Item"

):



    field = None



    try:



        field = amount_field(

            container,

            label

        )



        actual = read_amount(

            container,

            label

        )



        expected = money(expected)



        difference = abs(

            actual - expected

        )



        passed = (

            difference <= TOLERANCE

        )



        print(

            f"{'PASS' if passed else 'FAIL'} | "

            f"{prefix} {label} | "

            f"Expected={expected} | "

            f"Actual={actual} | "

            f"Difference={difference}"

        )



        check(f"{prefix} {label}", passed, expected, actual, page=container.page)

        # Green on pass, red on failure.

        mark_calculation(

            field,

            passed,

            expected,

            actual,

            difference

        )



        if not passed:



            errors.append(

                f"MISMATCH | {prefix} {label} | "

                f"Expected={expected} | "

                f"Actual={actual} | "

                f"Difference={difference}"

            )



    except Exception as error:



        errors.append(

            f"READ ERROR | "

            f"{prefix} {label} | {error}"

        )



        print(errors[-1])
        check(f"{prefix} {label}", False, expected, str(error), page=container.page)



        if field is not None:

            mark_calculation(field, False)





# ============================================================

# FIND LPO ITEM CONTAINER

# ============================================================



def item_container(page):



    dialog = page.get_by_role(

        "dialog"

    )



    if (

        dialog.count() == 1

        and dialog.is_visible()

    ):

        return dialog



    qty = page.locator(

        '[id="LocalPOdetails_195.quantity"]'

    )



    expect(qty).to_be_visible()



    parents = qty.locator(

        "xpath=ancestor::*"

    )



    for i in range(parents.count()):



        parent = parents.nth(i)



        if (

            parent.is_visible()

            and parent.locator(

                '[id="LocalPOdetails_195.unitprice"]'

            ).count() == 1

            and parent.locator(

                '[id="LocalPOdetails_195.dispercent"]'

            ).count() == 1

            and parent.locator(

                "div.fieldPresentation"

            ).count() >= 4

        ):



            return parent



    raise RuntimeError(

        "Item popup container not identified"

    )





# ============================================================

# WAIT FOR ERP CALCULATIONS

# ============================================================



def wait_calculations(

    page,

    container,

    expected_gross

):



    end = time.monotonic() + 8



    while time.monotonic() < end:



        try:



            actual_gross = read_amount(

                container,

                "Gross Amount"

            )



            if abs(

                actual_gross - expected_gross

            ) <= TOLERANCE:



                return



        except Exception:

            pass



        page.wait_for_timeout(300)



    print(

        "Gross amount did not settle "

        "to expected value; checking "

        "all fields for diagnostics"

    )





# ============================================================

# VALIDATE LPO ITEM CALCULATIONS

# ============================================================



def validate_item(page):



    qty = decimal(

        page.locator(

            '[id="LocalPOdetails_195.quantity"]'

        ).input_value()

    )



    price = decimal(

        page.locator(

            '[id="LocalPOdetails_195.unitprice"]'

        ).input_value()

    )



    discount_pct = decimal(

        page.locator(

            '[id="LocalPOdetails_195.dispercent"]'

        ).input_value()

    )



    gross = money(qty * price)



    discount = money(

        gross * discount_pct / Decimal("100")

    )



    tax = money(

        (gross - discount)

        * TAX_RATE

        / Decimal("100")

    )



    net = money(

        gross - discount + tax

    )



    log(

        f"ITEM VALIDATION | "

        f"Quantity={qty} "

        f"Price={price} "

        f"Discount%={discount_pct} "

        f"PGST%={TAX_RATE}"

    )



    container = item_container(page)



    wait_calculations(

        page,

        container,

        gross

    )



    errors = []



    for label, value in (

        ("Gross Amount", gross),

        ("Discount Amount", discount),

        ("Tax Amount", tax),

        ("Net Amount", net)

    ):



        compare(

            container,

            label,

            value,

            errors

        )



    return {

        "gross": gross,

        "discount": discount,

        "tax": tax,

        "net": net

    }, errors





# ============================================================

# FIND SUMMARY INFO

# ============================================================



def summary_container(page):



    sections = page.locator(

        "div.section_presentation"

    )



    matches = []



    for i in range(sections.count()):



        area = sections.nth(i)



        if any(

            norm(text) == "summary info"

            for text in area.locator(

                "p"

            ).all_inner_texts()

        ):

            matches.append(area)



    if len(matches) != 1:



        raise RuntimeError(

            "Summary Info section "

            "is not uniquely found"

        )



    return matches[0]





# ============================================================

# VALIDATE SUMMARY CALCULATIONS

# ============================================================



def validate_summary(page, values):



    section = summary_container(page)



    errors = []



    net = money(

        values["gross"]

        - values["discount"]

        + values["tax"]

        + EXPECTED_CHARGES

    )



    for label, amount in (

        (

            "Total Gross Amount",

            values["gross"]

        ),

        (

            "Discount Amount",

            values["discount"]

        ),

        (

            "Tax Amount",

            values["tax"]

        ),

        (

            "Charges Amount",

            EXPECTED_CHARGES

        ),

        (

            "Net Amount",

            net

        )

    ):



        compare(

            section,

            label,

            amount,

            errors,

            prefix="Summary"

        )



    return errors





# ============================================================

# VALIDATE ITEM -> OK -> SUMMARY -> SAVE

# ============================================================



def validate_then_save(page, tax_label, print_snapshot=None):
    stage = "ITEM"



    try:



        if norm(tax_label) != "pgst":



            raise RuntimeError(

                "Selected Tax Definition is not PGST"

            )



        expected, errors = validate_item(page)



        if errors:



            # Failure evidence is required for dashboard runs:
            screenshot_failure(page, stage, errors)



            return False



        log(

            "ALL ITEM CALCULATIONS PASSED - CLICK OK"

        )



        ok = page.get_by_role(

            "button",

            name="ok",

            exact=True

        ).and_(

            page.locator(":visible")

        )



        expect(ok).to_have_count(1)



        if print_snapshot is not None:
            print_snapshot.update(capture_lpo_print_creation(page))
        ok.click()



        page.locator(

            '[id="LocalPOdetails_195.quantity"]'

        ).wait_for(

            state="hidden",

            timeout=TIMEOUT

        )



        stage = "SUMMARY"



        page.wait_for_timeout(600)



        errors = validate_summary(

            page,

            expected

        )



        if errors:



            # Failure evidence is required for dashboard runs:
            screenshot_failure(page, stage, errors)



            return False



        log(

            "ALL SUMMARY CALCULATIONS PASSED "

            "- SAVE LPO"

        )



        stage = "SAVE"



        save = page.get_by_role(

            "button",

            name="Save",

            exact=True

        ).and_(

            page.locator(":visible")

        )



        if save.count() == 0:



            save = page.get_by_role(

                "button",

                name="Save draft",

                exact=True

            ).and_(

                page.locator(":visible")

            )



        expect(save).to_have_count(1)

        expect(save).to_be_enabled()



        capture_lpo_print_summary(page, print_snapshot)
        save.click()



        print(

            "LPO Save button clicked; "

            "ERP persistence not yet "

            "independently verified"

        )



        return True



    except Exception as error:



        # Failure evidence is required for dashboard runs:
        screenshot_failure(page, stage, [str(error)])



        return False





# ============================================================

# CREATE LOCAL PURCHASE ORDER

# ============================================================



@stage('Local Purchase Order: validate and save', 'Configured calculations match and a unique newly saved LPO row is identified', verified=True)
def create_lpo(page, pi):


    # Snapshot visible list rows before creating this specific LPO.
    # This lets us safely identify its newly added row after Save.
    global_search(page, "LPO creation", "LPO Creation")
    page.locator(".ag-root:visible").first.wait_for(state="visible", timeout=TIMEOUT)
    previous_rows = {r["text"] for r in grid_rows(page)}


    log("LPO CREATION")



    page.get_by_role(

        "button",

        name="CREATE",

        exact=True

    ).click()



    # Purchase Category

    category = round_robin(

        page,

        "LocalPO_194.purchaseCategoryId"

    )



    # PO Reference

    reference = select_exact(

        page,

        page.locator(

            '[id="LocalPO_194.poreferenceId"]'

        ),

        "PurchaseIndent"

    )



    # Same Department as PI

    department = select_exact(

        page,

        find_department(page),

        pi["department"]

    )



    # Same Purchase Indent

    select_pi_reference(

        page,

        pi["transaction"]

    )



    # Vendor

    vendor = round_robin(

        page,

        "LocalPO_194.vendorId"

    )



    print("Captured PO vendor for later GRN:", vendor)

    # Payment Terms

    terms = round_robin(

        page,

        "LocalPO_194.paymenttermsId"

    )



    # Four-digit PO Number

    number = po_number(page)



    # Narration

    narration = (

        f"Local Purchase Order for item "

        f"{pi['item']}. "

        f"Purchase Indent: {pi['transaction']}. "

        f"Department: {department}. "

        f"Indent Quantity: {pi['qty']}. "

        f"Purchase Type: Local Purchase."

    )



    page.locator(

        'textarea[name="LocalPO_194.narration"]'

    ).fill(narration)



    # Open Local PO Details

    page.get_by_text(

        "Local PO Details",

        exact=False

    ).first.scroll_into_view_if_needed()



    icons = page.locator(

        'svg[data-testid="EditOutlinedIcon"]:visible'

    )



    if icons.count() != 1:



        raise RuntimeError(

            f"Expected one LPO Edit icon, "

            f"got {icons.count()}"

        )



    button = icons.first.locator(

        "xpath=ancestor::button[1]"

    )



    (

        button if button.count() == 1

        else icons.first

    ).click()



    # Quantity

    input_number(

        page,

        "LocalPOdetails_195.quantity",

        pi["qty"]

    )



    # Random Unit Price

    price = random.randint(1, 499)



    input_number(

        page,

        "LocalPOdetails_195.unitprice",

        price

    )



    # PGST: ERP predefined 15%

    tax = select_pgst(page)



    # Random Discount

    discount_pct = random.randint(1, 49)



    input_number(

        page,

        "LocalPOdetails_195.dispercent",

        discount_pct

    )



    # Verify values did not reset.

    verify_lpo_numeric_fields(

        page,

        pi["qty"],

        price,

        discount_pct

    )



    # Validate and Save only if correct.

    print_snapshot = capture_lpo_print_creation(page, pi, price, discount_pct)
    saved = validate_then_save(page, tax, print_snapshot=print_snapshot)



    result = {

        "status": (

            "LPO_SAVE_CLICKED_NOT_VERIFIED"

            if saved

            else "LPO_VALIDATION_FAILED_NOT_SAVED"

        ),

        "po_number": number,

        "category": category,

        "reference": reference,

        "department": department,

        "vendor": vendor,

        "payment_terms": terms,

        "tax_definition": tax,

        "item": pi["item"],

        "quantity": pi["qty"],

        "unit_price": price,
        "uom": pi.get("uom"),
        "tax_percentage": str(TAX_RATE),
        "charges": str(EXPECTED_CHARGES),
        "_print_creation": print_snapshot,

        "discount_percentage": discount_pct,

        "narration": narration

    }



    if saved:
        result["transaction"] = capture_created_lpo_number(page, previous_rows, pi["transaction"])
        result["status"] = "LPO_SAVED_ROW_IDENTIFIED"

    for key, value in result.items():

        print(f"{key}: {value}")



    return result





# ============================================================

# MAIN AUTOMATION

# ============================================================



# ============================================================
# LPO SUBMIT + FOUR USER APPROVALS
# ============================================================


# This pattern is based on the ERP-generated transaction, NOT the manually
# entered four-digit PO field. Example only: LPO/LEO/2026/941.
LPO_TRANSACTION_RE = re.compile(r"^LPO/[A-Za-z0-9_-]+/\d{4}/\d+$", re.I)


def extract_lpo_numbers_from_row(row):
    """Read ERP LPO transaction from an exact text cell or paragraph."""
    cells = row.locator(".ag-cell").all_inner_texts()
    matches = []
    for cell in cells:
        for line in cell.splitlines():
            candidate = line.strip()
            if LPO_TRANSACTION_RE.fullmatch(candidate) and candidate not in matches:
                matches.append(candidate)
    return matches


def capture_created_lpo_number(page, previous_rows, pi_number):
    """Get the newly saved LPO transaction from the refreshed creation grid.

    Never hardcode a sample ID or choose an old row just because it matches LPO.
    """
    log("CAPTURE GENERATED LPO TRANSACTION")
    page.locator(".ag-root:visible").first.wait_for(state="visible", timeout=TIMEOUT)
    deadline = time.monotonic() + 40
    last_debug = []
    while time.monotonic() < deadline:
        fresh = [r for r in grid_rows(page) if r["text"] not in previous_rows]
        last_debug = fresh
        candidates = []
        for entry in fresh:
            row = page.locator(
                f'.ag-center-cols-container .ag-row[row-index="{entry["index"]}"]'
            )
            for number in extract_lpo_numbers_from_row(row):
                if number.casefold() != pi_number.casefold():
                    candidates.append(number)
        unique = list(dict.fromkeys(candidates))
        if len(unique) == 1:
            captured = unique[0]
            print("CAPTURED NEW LPO:", captured)
            return captured
        if len(unique) > 1:
            raise RuntimeError(
                f"Multiple new LPO transactions appeared: {unique}; "
                "cannot safely select one"
            )
        page.wait_for_timeout(600)
    raise RuntimeError(
        "Unable to identify the newly saved LPO from changed list rows. "
        f"Changed rows: {last_debug[:6]}. "
        "Check whether the list was refreshed, filtered, or paginated."
    )


def exact_lpo_row(page, transaction):
    """Match full transaction in one grid cell, not a substring or sample."""
    if not LPO_TRANSACTION_RE.fullmatch(transaction):
        raise ValueError(f"Unexpected LPO transaction format: {transaction!r}")
    rows = page.locator(".ag-center-cols-container .ag-row")
    matches = []
    for i in range(rows.count()):
        row = rows.nth(i)
        if transaction in extract_lpo_numbers_from_row(row):
            matches.append(row.get_attribute("row-index"))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one visible row for {transaction}; "
            f"found {len(matches)}. Check filters/pagination."
        )
    return matches[0]


def wait_for_transaction_row(page, transaction, stage):
    page.locator(".ag-root:visible").first.wait_for(state="visible", timeout=TIMEOUT)
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        try:
            return exact_lpo_row(page, transaction)
        except RuntimeError:
            page.wait_for_timeout(600)
    raise RuntimeError(f"Exact LPO {transaction} not available for {stage}")


def click_back_after_approval(page, label):
    """Return from approval detail if ERP opened it; allow list-only actions."""
    page.wait_for_timeout(2000)
    back = page.get_by_role("button", name="Back", exact=True).and_(
        page.locator(":visible")
    )
    if back.count() == 1:
        back.click()
        print(f"Back clicked after {label}")
    elif back.count() == 0 and page.locator(".ag-root:visible").count() > 0:
        print(f"{label}: already on approval list; Back not required")
    else:
        raise RuntimeError(
            f"{label}: neither a unique Back button nor an approval list is visible"
        )


@stage('Local Purchase Order: submit', 'Submit is clicked for the exact LPO; final status needs an assertion', verified=False)
def submit_lpo(page, transaction):
    """Select the same LPO from the list and submit it using the existing grid locators."""
    log(f"LPO SUBMIT: {transaction}")
    # Save normally returns to the LPO Creation list view. If not, navigate
    # explicitly to that page so a PI/other grid cannot be selected by mistake.
    if page.locator(".ag-root:visible").count() == 0:
        global_search(page, "LPO creation", "LPO Creation")
    row_index = wait_for_transaction_row(page, transaction, "submission")
    select_grid_row(page, row_index)
    submit = page.get_by_role("button", name="SUBMIT", exact=True).and_(
        page.locator(":visible")
    )
    expect(submit).to_have_count(1, timeout=TIMEOUT)
    expect(submit).to_be_enabled(timeout=TIMEOUT)
    submit.click()
    print(f"SUBMIT clicked for exact LPO {transaction}; status not independently verified")
    # If the ERP opens a View page like PI, return to the list first.
    # If the ERP stays in the list, no Back button is required.
    page.wait_for_timeout(2000)
    back = page.get_by_role("button", name="Back", exact=True).and_(
        page.locator(":visible")
    )
    if back.count() == 1:
        back.click()
        print("Back clicked after LPO submission")
    return "SUBMIT_CLICKED_NOT_INDEPENDENTLY_VERIFIED"


@stage('Local Purchase Order: approval', 'Approval is clicked for the exact LPO; final status needs an assertion', verified=False)
def approve_lpo(page, transaction, username):
    """Approve exactly the saved LPO in the current logged-in account."""
    log(f"LPO APPROVAL: {username}: {transaction}")
    global_search(page, "LPO approval", "Purchase Order - LPO Approval")
    row_index = wait_for_transaction_row(page, transaction, f"approval by {username}")
    print(f"PASS: exact LPO found for {username}: {transaction}")
    select_grid_row(page, row_index)
    approve = page.get_by_role("button", name="Approve", exact=True).and_(
        page.locator(":visible")
    )
    expect(approve).to_have_count(1, timeout=TIMEOUT)
    expect(approve).to_be_enabled(timeout=TIMEOUT)
    approve.click()
    print(f"Approve clicked for {transaction} by {username}; verify status in ERP")
    click_back_after_approval(page, f"LPO approval by {username}")
    return "APPROVE_CLICKED_NOT_INDEPENDENTLY_VERIFIED"



# ============================================================
# OPEN GRN CREATION AFTER FINAL LPO APPROVAL
# ============================================================

def open_grn_creation(page, lpo_transaction):
    """Navigate to exact 'Goods Receipt Note' process and open CREATE form.

    This does not fill, save or submit any GRN.
    """
    log(f"OPEN GOODS RECEIPT NOTE AFTER LPO APPROVAL: {lpo_transaction}")

    # Use the exact process name shown in your ERP global search.
    global_search(page, "Goods Receipt Note", "Goods Receipt Note")

    # The process typically opens a list view with an AG Grid.
    page.locator(".ag-root:visible").first.wait_for(
        state="visible", timeout=TIMEOUT
    )

    create = page.get_by_role("button", name="CREATE", exact=True).and_(
        page.locator(":visible")
    )
    expect(create).to_have_count(1, timeout=TIMEOUT)
    expect(create).to_be_enabled(timeout=TIMEOUT)
    create.click()

    # Captured on your Goods Receipt Note create form.
    grn_reference = page.locator('[id="GoodsReceiptNote_94.grnreferenceId"]')
    expect(grn_reference).to_be_visible(timeout=TIMEOUT)

    print("PASS: Goods Receipt Note -> CREATE form opened")
    print("LPO transaction:", lpo_transaction)
    print("GRN NOT SAVED")
    return "GRN_CREATE_FORM_OPENED_NOT_SAVED"


# ============================================================
# GRN CREATION FOR THE EXACT APPROVED LPO
# ============================================================

def grn_field(page, suffix):
    return page.locator('[id=' + json.dumps('GoodsReceiptNote_94.' + suffix) + ']')


def grn_select_matching(page, field, expected, contains=False):
    """Select one enabled, visible option; never silently pick a different record."""
    open_dropdown(page, field)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        options = dropdown_options(page, field)
        values = []
        for i in range(options.count()):
            option = options.nth(i)
            if not option.is_enabled():
                continue
            label = option.inner_text().strip()
            if ((norm(expected) in norm(label)) if contains else (norm(expected) == norm(label))):
                values.append(label)
        if len(values) == 1:
            select_option(page, field, values[0])
            return values[0]
        if len(values) > 1:
            raise RuntimeError(f'GRN option is ambiguous: {expected!r} -> {values}')
        if field.get_attribute('readonly') is None:
            field.fill(str(expected))
        page.wait_for_timeout(500)
    raise RuntimeError(f'GRN option not found: {expected!r}')



def grn_select_po_vendor(page, field, saved_po_vendor):
    """Search and CLICK a unique MUI vendor-master option.

    Vendor labels may use either '141 - NAME' or 'NAME - 141'.
    Typing alone is NOT a committed master-data selection.
    """
    def parse_vendor(value):
        raw = ' '.join(str(value or '').split())
        leading = re.match(r'^\s*(\d+)\s*-\s*(.+?)\s*$', raw)
        trailing = re.match(r'^\s*(.+?)\s*-\s*(\d+)\s*$', raw)
        if leading:
            return norm(leading.group(2)), leading.group(1)
        if trailing:
            return norm(trailing.group(1)), trailing.group(2)
        return norm(raw), None

    expected_name, expected_code = parse_vendor(saved_po_vendor)
    if not expected_name:
        raise RuntimeError('PO vendor is missing')

    expect(field).to_be_visible(timeout=TIMEOUT)
    field.click()
    # Search by the name, not its optional numeric master ID.
    search_text = re.sub(r'^\s*\d+\s*-\s*', '', str(saved_po_vendor)).strip()
    search_text = re.sub(r'\s*-\s*\d+\s*$', '', search_text).strip()
    field.fill(search_text)

    deadline = time.monotonic() + 30
    last_options = []
    while time.monotonic() < deadline:
        options = page.locator('[role="option"]:visible')
        matches = []
        last_options = []
        for index in range(options.count()):
            option = options.nth(index)
            if not option.is_enabled():
                continue
            label = option.inner_text().strip()
            last_options.append(label)
            name, code = parse_vendor(label)
            if name == expected_name and (not expected_code or not code or code == expected_code):
                matches.append((label, option))

        if len(matches) > 1:
            raise RuntimeError(f'Ambiguous matching GRN vendor masters: {[x[0] for x in matches]}')
        if len(matches) == 1:
            label, option = matches[0]
            # CRITICAL: click the real dropdown option to commit the master ID.
            option.scroll_into_view_if_needed()
            option.click(timeout=TIMEOUT)
            expect(field).to_have_attribute('aria-expanded', 'false', timeout=TIMEOUT)
            value = field.input_value().strip()
            actual_name, actual_code = parse_vendor(value)
            if actual_name != expected_name or (expected_code and actual_code and expected_code != actual_code):
                raise RuntimeError(f'GRN vendor did not commit: expected {saved_po_vendor!r}; got {value!r}')
            print('PASS: clicked GRN vendor MASTER option:', label)
            return value

        page.wait_for_timeout(350)

    raise RuntimeError(f'No unique vendor master found for {saved_po_vendor!r}; visible options={last_options!r}')


def grn_select_exact_po(page, field, po_number):
    """Commit exact PO invoice/reference by clicking its master dropdown option."""
    expected = str(po_number).strip()
    if not expected:
        raise RuntimeError('Missing approved LPO transaction')
    field.wait_for(state='visible', timeout=TIMEOUT)
    field.click()
    if field.get_attribute('readonly') is None:
        field.fill(expected)
    pattern = re.compile(r'^\s*' + re.escape(expected) + r'(?=\s*(?:-|$))', re.I)
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        options = dropdown_options(page, field)
        matches = []
        for i in range(options.count()):
            opt = options.nth(i)
            if opt.is_enabled():
                label = opt.inner_text().strip()
                if pattern.search(label):
                    matches.append((label, opt))
        if len(matches) > 1:
            raise RuntimeError(f'Ambiguous LPO master options: {[x[0] for x in matches]}')
        if len(matches) == 1:
            label, option = matches[0]
            option.click()  # REQUIRED: commits PO record to GRN
            expect(field).to_have_value(label, timeout=TIMEOUT)
            field.press('Tab')
            if field.get_attribute('aria-expanded') == 'true':
                raise RuntimeError('LPO dropdown remained expanded')
            print('PASS: clicked same approved LPO master option:', label)
            return label
        page.wait_for_timeout(350)
    raise RuntimeError(f'Cannot find selectable PO master record {expected!r}')


def start_emergency_stop_button():
    """Separate STOP window; works even during a blocking Playwright wait.

    Clicking STOP forcibly ends this automation Python process. It is not a
    graceful logout/save. Supported when desktop Tkinter is available.
    """
    stop_ui = r'''import os,sys,signal,tkinter as tk
parent_pid=int(sys.argv[1])
root=tk.Tk()
root.title('ERP AUTOMATION - EMERGENCY STOP')
root.geometry('340x135')
root.attributes('-topmost',True)
tk.Label(root,text='Stop ERP automation immediately',font=('Arial',11)).pack(pady=13)
def stop_now():
    os.kill(parent_pid,signal.SIGTERM)
    root.destroy()
tk.Button(root,text='STOP AUTOMATION',bg='#bb2020',fg='white',font=('Arial',12,'bold'),command=stop_now).pack(fill='x',padx=20)
root.mainloop()
'''
    try:
        return subprocess.Popen([sys.executable, '-c', stop_ui, str(os.getpid())],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except OSError as exc:
        print('STOP button unavailable:', exc)
        print('Use Ctrl+C in the terminal to stop the automation.')
        return None














# ============================================================
# AUTOMATIC PDF PRINT VALIDATION (OPTIONAL, NON-INTRUSIVE)
# ============================================================
# Install once: pip install pymupdf
# The browser PDF viewer's thumbnail canvas is NOT the ERP print document.
# This listener captures actual PDF network responses or PDF downloads.
# PDFs generated solely as browser blob URLs may need a separate print hook.
# If a document is not captured, report NOT_CAPTURED (not a false PASS).
# Configure printed fields per ERP template below.

# ============================================================
# STRICT CREATION -> PRINT VALIDATION, v1
# ============================================================
# Uses only the actual captured PDF. No OCR or fuzzy item-code matching.
# Missing/ambiguous mappings are REVIEW, never a fabricated PASS.
# Original source PDFs are kept; annotations are written to copies.

PRINT_VALIDATION_VERSION = 'strict-print-v1'
PRINT_REPORTS = (run_directory() or BASE / 'reports') / 'print_validation'
PRINT_REQUIRE_PDF = False  # Optional approval actions may not produce a PDF.
PRINT_CAPTURE_WAIT_MS = 2500
PRINT_PREVIEW_ENABLED = True
PRINT_PREVIEW_DURATION_MS = 5000
PRINT_CAPTURE_MAX_BYTES = 15 * 1024 * 1024
PRINT_STOP_ON_MISMATCH = False  # Record all discrepancies; do not retry transactions.
PRINT_AMOUNT_TOLERANCE = Decimal('0')  # 12 and 12.00 match; 12 and 12.01 do not.
PRINT_MAX_PAGES = 100

# Template labels, not ERP locators. Exact label aliases only.
# Add verified aliases for your actual print template here. Do not map a generic
# 'Amount' column to Gross/Net until the template's meaning is known.
PRINT_TABLE_ALIASES = {
    'row_no': ('S.No', 'S No', 'Sl.No', 'Sl No', 'Sr.No', 'Serial No', '#'),
    'item_code': ('Item Code', 'Material Code', 'Product Code'),
    'item_name': ('Item Name', 'Material Name', 'Item Description', 'Description'),
    'item': ('Item', 'Material', 'Product'),
    'uom': ('UOM', 'UoM', 'Unit of Measure', 'Unit'),
    'quantity': ('Qty', 'Quantity', 'Indent Qty', 'Indent Quantity', 'Order Qty'),
    'received_qty': ('Received Qty', 'Received Quantity', 'Qty / Accepted Qty', 'Accepted Qty'),
    'reference_qty': ('Reference Qty', 'PO Qty', 'Ordered Qty'),
    'unit_price': ('Unit Price', 'Unit Rate', 'Rate', 'Price'),
    'previous_price': ('Previous Price', 'Previous Purchase Price', 'Last Purchase Price'),
    'discount_percentage': ('Discount %', 'Discount Percent', 'Discount Percentage', 'Disc %'),
    'discount_amount': ('Discount Amount', 'Discount Value', 'Disc Amount'),
    'tax_percentage': ('Tax %', 'Tax Rate', 'PGST %', 'VAT %'),
    'tax_amount': ('Tax Amount', 'Tax Value', 'PGST Amount', 'VAT Amount'),
    'gross': ('Gross Amount', 'Gross Value', 'Line Gross'),
    'net': ('Net Amount', 'Net Value', 'Line Total'),
    'charges': ('Charges Amount', 'Charges'),
    'unmapped_amount': ('Amount', 'Total'),
}
PRINT_HEADER_ALIASES = {
    'PI': {
        'transaction': ('Indent No', 'Indent Number', 'PI No', 'Transaction No'),
        'date': ('Required Date',),  # Indent Date is NOT necessarily Required Date.
        'department': ('Department',), 'purchase': ('Purchase Type',),
        'kind': ('Indent Type',), 'section': ('Section',), 'asset': ('Equipment', 'Asset'),
    },
    'LPO': {
        'transaction': ('LPO No', 'LPO Number', 'Transaction No', 'PO No', 'PO Number'),
        'department': ('Department',), 'vendor': ('Vendor', 'Supplier'),
    },
    'GRN': {
        'transaction': ('GRN No', 'GRN Number', 'Goods Receipt Note No', 'Transaction No'),
        'po_reference': ('Local PO', 'PO Reference', 'LPO No'),
        'vendor': ('Vendor', 'Supplier'), 'invoice_no': ('Invoice No', 'Invoice Number'),
        'invoice_date': ('Invoice Date',), 'description': ('Description',),
    },
}
PRINT_TOTAL_ALIASES = {
    'gross': ('Total Gross Amount', 'Gross Amount', 'Gross Value'),
    'discount_amount': ('Total Discount Amount', 'Discount Amount', 'Discount Value'),
    'tax_amount': ('Total Taxes Amount', 'Total Tax Amount', 'Tax Amount', 'VAT Amount', 'PGST Amount'),
    'charges': ('Charges Amount', 'Total Charges', 'Charges'),
    'net': ('Total Net Amount', 'Net Amount', 'Grand Total', 'Net Payable'),
}
# Read-only capture through fieldPresentation/MuiFormLabel markup already used
# in this script. Unknown/duplicate labels produce None, not invented values.
PRINT_CREATION_LABELS = {
    'item': ('Item', 'Item Name'),
    'item_code': ('Item Code',),
    'uom': ('UOM', 'UoM', 'Unit of Measure'),
    'unit_price': ('Unit Price', 'Unit Rate'),
    'discount_percentage': ('Discount Percentage', 'Discount %'),
    'tax_percentage': ('Tax Percentage', 'Tax %'),
    'gross': ('Gross Amount',),
    'discount_amount': ('Discount Amount',),
    'tax_amount': ('Tax Amount',),
    'charges': ('Charges Amount',),
    'net': ('Net Amount',),
}
_PV_NUMERIC = {'quantity', 'received_qty', 'reference_qty', 'unit_price',
               'discount_percentage', 'tax_percentage', 'gross',
               'discount_amount', 'tax_amount', 'charges', 'net'}
_PV_MONEY = {'gross', 'discount_amount', 'tax_amount', 'charges', 'net'}
_PV_COL_LOOKUP = None


def print_safe_name(value):
    return re.sub(r'[^a-zA-Z0-9_-]+', '_', str(value))[:100]


def print_normalized(value):
    import unicodedata
    return ' '.join(unicodedata.normalize('NFKC', str(value)).split()).casefold()


def print_is_pdf(data):
    return bool(data and data.lstrip()[:5] == b'%PDF-')


def _pv_label(value):
    return re.sub(r'[^a-z0-9%#]+', '', print_normalized(value))


def _pv_text(value):
    import unicodedata
    return ' '.join(unicodedata.normalize('NFKC', str(value or '')).split())


def _pv_number(value):
    """Parse ONE decimal, never concatenate numbers or strip arbitrary words."""
    if value is None or isinstance(value, bool):
        raise ValueError('Missing numeric value')
    text = _pv_text(value).replace('\u2212', '-')
    negative = text.startswith('(') and text.endswith(')')
    if negative:
        text = text[1:-1].strip()
    currency = r'(?:INR|USD|SLE|SLL|Rs\.?|Le\.?|\$|\u20b9|\u00a3|\u20ac)'
    text = re.sub(r'^' + currency + r'\s*', '', text, flags=re.I)
    text = re.sub(r'\s*' + currency + r'$', '', text, flags=re.I)
    if text.endswith('%'):
        text = text[:-1].strip()
    # Conventional comma grouping and Indian grouping; decimal separator is dot.
    pattern = r'[+-]?(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})+,\d{3})(?:\.\d+)?'
    if not re.fullmatch(pattern, text):
        raise ValueError('Not one unambiguous decimal: ' + repr(text))
    result = Decimal(text.replace(',', ''))
    if not result.is_finite():
        raise ValueError('Non-finite decimal')
    if negative:
        if result < 0:
            raise ValueError('Conflicting negative signs')
        result = -result
    return result


def _pv_equivalent(key, actual, expected):
    if key in _PV_NUMERIC:
        delta = abs(_pv_number(actual) - _pv_number(expected))
        return delta <= (PRINT_AMOUNT_TOLERANCE if key in _PV_MONEY else Decimal('0'))
    if key in ('item_code', 'transaction', 'po_reference', 'invoice_no'):
        # Preserve punctuation, case and leading zeroes; no similarity scoring.
        return _pv_text(actual) == _pv_text(expected)
    if key == 'vendor':
        def vendor_parts(v):
            t = _pv_text(v)
            match = re.fullmatch(r'(\d+)\s+-\s+(.+)', t)
            if match:
                return match.group(2).casefold(), match.group(1)
            match = re.fullmatch(r'(.+)\s+-\s+(\d+)', t)
            return (match.group(1).casefold(), match.group(2)) if match else (t.casefold(), None)
        left, right = vendor_parts(actual), vendor_parts(expected)
        return left[0] == right[0] and (left[1] is None or right[1] is None or left[1] == right[1])
    if key in ('date', 'invoice_date'):
        return _pv_text(actual).replace('-', '/') == _pv_text(expected).replace('-', '/')
    return print_normalized(actual) == print_normalized(expected)


def _pv_split_item(value):
    text = _pv_text(value)
    # Only split the same explicit CODE - NAME format used in the supplied script.
    match = re.fullmatch(r'([A-Za-z0-9_.\-/]+)\s+-\s+(.+)', text)
    if match:
        return {'item_code': match.group(1), 'item_name': match.group(2)}
    return {'item_name': text} if text else {}


def _pv_copy(value):
    return json.loads(json.dumps(value, default=str))


def _pv_read_labeled(scope, aliases):
    """A missing capture is reported as unavailable; no guessed ERP IDs."""
    for alias in aliases:
        try:
            containers = scope.locator('div.fieldPresentation')
            matches = []
            for i in range(containers.count()):
                c = containers.nth(i)
                if not c.is_visible():
                    continue
                labels = c.locator('span.MuiFormLabel-root')
                if labels.count() != 1 or norm(labels.inner_text().replace('*', '')) != norm(alias):
                    continue
                inputs = c.locator('input:visible, textarea:visible')
                if inputs.count() == 1:
                    value = inputs.input_value().strip()
                elif inputs.count() == 0:
                    pieces = [t.strip() for t in c.inner_text().splitlines() if t.strip()]
                    pieces = [t for t in pieces if norm(t.replace('*', '')) != norm(alias)
                              and not t.startswith(('PASS |', 'FAIL |', 'PASS -', 'FAIL -'))]
                    value = pieces[0] if len(pieces) == 1 else None
                else:
                    value = None
                matches.append(value)
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                return None
        except Exception:
            continue
    return None


def _pv_labeled_snapshot(scope):
    return {key: _pv_read_labeled(scope, aliases)
            for key, aliases in PRINT_CREATION_LABELS.items()}


def _pv_read_input(page, selector):
    try:
        field = page.locator(selector)
        if field.count() == 1 and field.is_visible():
            return field.input_value().strip()
    except Exception:
        pass
    return None


def capture_pi_print_creation(page, item, quantity, uom):
    field = page.locator('[id="PurchaseIndentItemDetails_92.indentQty"]')
    dialog = page.get_by_role('dialog').filter(has=field)
    scope = dialog if dialog.count() == 1 else page
    values = _pv_labeled_snapshot(scope)
    values.update(item=_pv_read_input(page, '[id="PurchaseIndentItemDetails_92.itemId"]'),
                  quantity=_pv_read_input(page, '[id="PurchaseIndentItemDetails_92.indentQty"]'), uom=uom)
    return {'item': values, 'summary': {}, 'source': 'PI item editor, before Item OK'}


def capture_lpo_print_creation(page, pi=None, unit_price=None, discount_percentage=None):
    values = _pv_labeled_snapshot(item_container(page))
    for key, suffix in (('quantity', 'quantity'), ('unit_price', 'unitprice'),
                        ('discount_percentage', 'dispercent')):
        values[key] = _pv_read_input(page, '[id="LocalPOdetails_195.' + suffix + '"]')
    # Amounts were validated by the existing validate_item/validate_summary logic.
    for key, label in (('gross', 'Gross Amount'), ('discount_amount', 'Discount Amount'),
                       ('tax_amount', 'Tax Amount'), ('net', 'Net Amount')):
        try:
            values[key] = str(read_amount(item_container(page), label))
        except Exception:
            values[key] = None
    return {'item': values, 'summary': {}, 'source': 'LPO item editor, before Item OK'}


def capture_lpo_print_summary(page, snapshot):
    if snapshot is None:
        return
    for key, label in (('gross', 'Total Gross Amount'), ('discount_amount', 'Discount Amount'),
                       ('tax_amount', 'Tax Amount'), ('charges', 'Charges Amount'), ('net', 'Net Amount')):
        try:
            snapshot['summary'][key] = str(read_amount(summary_container(page), label))
        except Exception:
            snapshot['summary'][key] = None
    snapshot['summary_source'] = 'LPO Summary Info, immediately before Save'


def capture_grn_print_item(page, quantity):
    heading = page.get_by_text('Edit GRN Item Details', exact=True)
    dialog = page.get_by_role('dialog').filter(has=heading)
    scope = dialog if dialog.count() == 1 else page
    values = _pv_labeled_snapshot(scope)
    values['received_qty'] = str(quantity)
    page._strict_grn_print_creation = {
        'item': values, 'summary': {},
        'source': 'GRN item editor and verified warehouse quantity, before item OK',
    }


def capture_grn_print_summary(page):
    snapshot = getattr(page, '_strict_grn_print_creation', {'item': {}, 'summary': {}})
    try:
        scope = summary_container(page)
    except Exception:
        scope = None
    for key, aliases in PRINT_TOTAL_ALIASES.items():
        snapshot['summary'][key] = _pv_read_labeled(scope, aliases) if scope is not None else None
    page._strict_grn_print_creation = snapshot


def _pv_baseline(document_type, expected):
    """Keep entered/selected, displayed and calculated values separately."""
    snap = expected.get('_print_creation') or {}
    screen = snap.get('item') or {}
    header = {key: expected.get(key) for key in PRINT_HEADER_ALIASES[document_type]
              if expected.get(key) is not None}
    header.setdefault('transaction', None)
    item = _pv_split_item(expected.get('item'))
    known_uom = expected.get('uom') if expected.get('uom') is not None else screen.get('uom')
    if known_uom is not None:
        item['uom'] = known_uom
    totals = {}
    calculated = {}
    if document_type == 'PI':
        item['quantity'] = expected.get('qty')
        for key in _PV_NUMERIC - {'quantity', 'reference_qty', 'received_qty'}:
            if screen.get(key) is not None:
                item[key] = screen[key]
    elif document_type == 'LPO':
        item.update(quantity=expected.get('quantity'), unit_price=expected.get('unit_price'))
        for key in ('discount_percentage',):
            item[key] = expected.get(key)
        item['tax_percentage'] = str(expected.get('tax_percentage', TAX_RATE))
        try:
            gross = money(_pv_number(item['quantity']) * _pv_number(item['unit_price']))
            disc = money(gross * _pv_number(item['discount_percentage']) / Decimal('100'))
            tax = money((gross - disc) * _pv_number(item['tax_percentage']) / Decimal('100'))
            calculated = dict(gross=str(gross), discount_amount=str(disc),
                              tax_amount=str(tax), net=str(money(gross - disc + tax)))
            item.update(calculated)
            charges = _pv_number(expected.get('charges', EXPECTED_CHARGES))
            totals = {**calculated, 'charges': str(charges),
                      'net': str(money(gross - disc + tax + charges))}
        except (ValueError, ArithmeticError):
            totals = {k: None for k in PRINT_TOTAL_ALIASES}
    elif document_type == 'GRN':
        item['received_qty'] = expected.get('received_qty')
        # Do not assume the GRN's unit price/totals equal the LPO. Use the GRN UI.
        for key in _PV_NUMERIC - {'received_qty', 'quantity', 'reference_qty'}:
            if screen.get(key) is not None:
                item[key] = screen[key]
        totals = {k: v for k, v in (snap.get('summary') or {}).items() if v is not None}
    screen_item = {k: v for k, v in screen.items() if k != 'item'}
    screen_item.update(_pv_split_item(screen.get('item')))
    if screen.get('item_code') is not None:
        screen_item['item_code'] = screen['item_code']
    return _pv_copy({'version': PRINT_VALIDATION_VERSION, 'document_type': document_type,
                     'header': header, 'items': [item], 'totals': totals,
                     'screen_items': [screen_item], 'screen_totals': snap.get('summary', {}),
                     'source': snap.get('source', 'Values supplied by the existing creation workflow'),
                     'calculated_item_amounts': calculated})


def _pv_column(text):
    key = _pv_label(text)
    candidates = [name for name, aliases in PRINT_TABLE_ALIASES.items()
                  if any(_pv_label(a) == key for a in aliases)]
    return candidates[0] if len(candidates) == 1 else None


def _pv_words(page):
    return [tuple(w) for w in page.get_text('words', sort=True) if str(w[4]).strip()]


def _pv_lines(words):
    # Geometric rows, not PDF storage order. Preserve column positions.
    lines = []
    for word in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        cy = (word[1] + word[3]) / 2
        match = next((x for x in reversed(lines[-4:]) if abs(x['cy'] - cy) <= 3.0), None)
        if match is None:
            lines.append({'cy': cy, 'words': [word]})
        else:
            match['words'].append(word)
    return [sorted(line['words'], key=lambda w: w[0]) for line in sorted(lines, key=lambda x: x['cy'])]


def _pv_rect(words):
    if not words:
        return None
    return [min(w[0] for w in words), min(w[1] for w in words),
            max(w[2] for w in words), max(w[3] for w in words)]


def _pv_cell(text, rect, page_no, method):
    return {'text': _pv_text(text), 'bbox': list(rect) if rect is not None else None,
            'page': page_no + 1, 'method': method}


def _pv_in_rect(word, box):
    return box[0] <= (word[0] + word[2]) / 2 <= box[2] and box[1] <= (word[1] + word[3]) / 2 <= box[3]


def _pv_ruled_rows(page, page_no):
    rows, regions = [], []
    if not hasattr(page, 'find_tables'):
        return rows, regions
    try:
        tables = page.find_tables().tables
    except Exception:
        return rows, regions
    for table in tables:
        names = list(table.header.names or [])
        columns = [_pv_column(x or '') for x in names]
        if not any(c in columns for c in ('item_code', 'item_name', 'item')):
            continue
        if not any(c in columns for c in ('quantity', 'received_qty', 'unit_price')):
            continue
        recognized = [c for c in columns if c is not None]
        if len(recognized) != len(set(recognized)):
            continue  # Duplicate named columns must not silently replace each other.
        data = table.extract()
        if not data:
            continue
        first = 0 if table.header.external else 1
        parsed = []
        for idx in range(first, len(data)):
            values = data[idx]
            if not any(v is not None and str(v).strip() for v in values):
                continue
            if all(_pv_column(values[j] or '') == col for j, col in enumerate(columns) if col):
                continue  # Repeated table header.
            cells = table.rows[idx].cells
            row = {col: _pv_cell(values[j], cells[j], page_no, 'ruled table')
                   for j, col in enumerate(columns) if col and j < len(values)}
            identity = ' '.join(row.get(k, {}).get('text', '') for k in ('item_code', 'item_name', 'item')).strip()
            total_labels = {_pv_label(a) for v in PRINT_TOTAL_ALIASES.values() for a in v}
            if _pv_label(identity) in total_labels | {'total', 'subtotal', 'grandtotal'}:
                continue
            if identity:
                parsed.append(row)
        if parsed:
            rows.extend(parsed)
            bottom = max(c['bbox'][3] for r in parsed for c in r.values() if c.get('bbox'))
            regions.append([table.bbox[0], table.bbox[1], table.bbox[2], bottom])
    return rows, regions


def _pv_header_spans(line):
    found, used = [], set()
    # Longest aliases first to avoid Price matching within Previous Price.
    aliases = sorted(((key, alias) for key, values in PRINT_TABLE_ALIASES.items() for alias in values),
                     key=lambda v: len(_pv_label(v[1])), reverse=True)
    for key, alias in aliases:
        target = _pv_label(alias)
        for start in range(len(line)):
            for size in range(1, min(6, len(line) - start) + 1):
                inds = set(range(start, start + size))
                if inds & used:
                    continue
                sample = line[start:start + size]
                if _pv_label(' '.join(w[4] for w in sample)) != target:
                    continue
                if any(b[0] - a[2] > 18 for a, b in zip(sample, sample[1:])):
                    continue
                found.append((key, _pv_rect(sample)))
                used.update(inds)
    # Preserve unknown header words as boundaries so they cannot enter a field.
    for idx, word in enumerate(line):
        if idx not in used:
            found.append(('_unmapped_' + str(idx), list(word[:4])))
    return sorted(found, key=lambda x: x[1][0])


def _pv_borderless_rows(page, page_no, words):
    rows, regions = [], []
    lines = _pv_lines(words)
    for i, line in enumerate(lines):
        spans = _pv_header_spans(line)
        keys = [s[0] for s in spans]
        if not any(k in keys for k in ('item_code', 'item_name', 'item')):
            continue
        if not any(k in keys for k in ('quantity', 'received_qty')):
            continue
        if len(keys) != len(set(keys)):
            continue
        centers = [(box[0] + box[2]) / 2 for _, box in spans]
        bounds = []
        for j, (key, box) in enumerate(spans):
            # Use the gap between adjacent header boxes, not the centers of long names.
            left = (spans[j-1][1][2] + box[0]) / 2 if j else max(page.rect.x0, box[0] - 30)
            right = (box[2] + spans[j+1][1][0]) / 2 if j + 1 < len(spans) else page.rect.x1
            bounds.append((key, left, right))
        header_bottom = max(w[3] for w in line)
        candidates = []
        for next_line in lines[i + 1:]:
            y = min(w[1] for w in next_line)
            if y - header_bottom > 220:
                break
            text = _pv_text(' '.join(w[4] for w in next_line))
            if re.search(r'^(?:total |gross amount|discount amount|tax amount|charges amount|net amount|grand total|terms|approved|prepared|signature)', text, re.I):
                break
            if sum(_pv_column(w[4]) is not None for w in next_line) > 3:
                break
            row = {}
            for key, left, right in bounds:
                cell_words = [w for w in next_line if left <= (w[0] + w[2])/2 < right]
                if not key.startswith('_unmapped_'):
                    row[key] = _pv_cell(' '.join(w[4] for w in cell_words), _pv_rect(cell_words), page_no, 'borderless row')
            identity = any(row.get(k, {}).get('text') for k in ('item_code', 'item_name', 'item'))
            numeric = any(row.get(k, {}).get('text') for k in ('quantity', 'received_qty'))
            if identity and numeric:
                candidates.append(row)
            elif any(row.get(k, {}).get('text') for k in ('item_name', 'item', 'item_code')) and candidates:
                # Wrapping needs a verified template/grid. Do not silently drop extra text.
                for c in candidates[-1].values():
                    c['ambiguous'] = True
        if candidates:
            rows.extend(candidates)
            last_y = max(c.get('bbox', [0, 0, 0, header_bottom])[3] for r in candidates for c in r.values() if c.get('bbox'))
            regions.append([page.rect.x0, min(w[1] for w in line)-1, page.rect.x1, last_y+1])
    return rows, regions


def _pv_label_candidates(words, aliases, page_no, regions=(), numeric=False, table_floor=None):
    lines = _pv_lines(words)
    # Alias priority is intentional: e.g. LPO No before generic PO No.
    for alias in aliases:
        candidates = []
        target = _pv_label(alias)
        for line in lines:
            for start in range(len(line)):
                for size in range(1, min(7, len(line)-start)+1):
                    sample = line[start:start+size]
                    if _pv_label(' '.join(w[4] for w in sample)) != target:
                        continue
                    box = _pv_rect(sample)
                    if any(_pv_in_rect(sample[0], reg) for reg in regions):
                        continue
                    # Numeric totals must be below the last item table on this page.
                    if table_floor is not None and box[1] < table_floor - 2:
                        continue
                    if any(b[0]-a[2] > 18 for a,b in zip(sample,sample[1:])):
                        continue
                    # A suffix of a longer label is not the same label.
                    if start and _pv_label(line[start-1][4]) in ('total','previous','reference','subtotal','net','gross','unit'):
                        continue
                    after = line[start+size:]
                    while after and after[0][4] in (':', '='):
                        after = after[1:]
                    # Stop before a second labeled field on the same line.
                    all_labels = [a for d in PRINT_HEADER_ALIASES.values() for v in d.values() for a in v]
                    all_labels += [a for v in PRINT_TOTAL_ALIASES.values() for a in v]
                    cut = len(after)
                    for j in range(len(after)):
                        for n in range(1, min(6, len(after)-j)+1):
                            if any(_pv_label(' '.join(w[4] for w in after[j:j+n])) == _pv_label(a) for a in all_labels):
                                cut = min(cut, j)
                    after = after[:cut]
                    if not after:
                        # Only a directly-below value aligned with the label; otherwise REVIEW.
                        below = [w for w in words if box[3] <= w[1] <= box[3]+22
                                 and box[0]-3 <= w[0] <= box[2]+12
                                 and not any(_pv_in_rect(w, reg) for reg in regions)]
                        if below:
                            nearest = min(w[1] for w in below)
                            after = sorted([w for w in below if abs(w[1]-nearest)<3],key=lambda w:w[0])
                    if not after:
                        candidates.append(_pv_cell('', box, page_no, 'missing labeled value'))
                        continue
                    # One printed value only. Never search elsewhere for the expected number.
                    value = _pv_text(' '.join(w[4] for w in after)).lstrip(': ').strip()
                    candidates.append(_pv_cell(value, _pv_rect(after), page_no, 'labeled value'))
        if candidates:
            return candidates
    return []


def _pv_extract(pdf):
    rows, pages, regions = [], [], {}
    for i, page in enumerate(pdf):
        words = _pv_words(page)
        r, boxes = _pv_ruled_rows(page, i)
        if not r:
            r, boxes = _pv_borderless_rows(page, i, words)
        rows.extend(r)
        pages.append(words)
        regions[i] = boxes
    return rows, pages, regions


def _pv_field(key, expected, cell, *, group, screen=None, screen_required=False, reason=None):
    actual = cell.get('text') if cell else None
    field = {'field': group + '.' + key, 'key': key, 'expected': None if expected is None else str(expected),
             'actual': actual, 'creation_screen': None if screen is None else str(screen),
             'status': 'UNMAPPED', 'reason': reason or '',
             'page': cell.get('page') if cell else None, 'bbox': cell.get('bbox') if cell else None}
    if expected is None:
        field['status'] = 'MISSING_CREATION_VALUE'
        field['reason'] = reason or 'No trustworthy creation value was captured; print cannot establish its own expectation.'
        return field
    if not cell or actual is None or not str(actual).strip() or cell.get('ambiguous'):
        field['reason'] = reason or 'Missing, ambiguous or unsupported printed field/table layout.'
        return field
    try:
        same = _pv_equivalent(key, actual, expected)
        screen_same = _pv_equivalent(key, screen, expected) if screen is not None else True
    except (ValueError, ArithmeticError) as exc:
        field['status'] = 'UNREADABLE_VALUE'
        field['reason'] = str(exc)
        return field
    field['status'] = 'PASS' if same and screen_same else 'FAIL'
    field['reason'] = ('Creation and printed values agree.' if same and screen_same
                       else 'Printed value differs from creation.' if not same else 'Creation screen differs from entered/calculated value.')
    if same and screen_same and screen_required and screen is None:
        field['status'] = 'MISSING_CREATION_VALUE'
        field['reason'] = 'Printed value matches expectation, but creation screen value was not captured.'
    if key in _PV_NUMERIC:
        field['difference'] = str(_pv_number(actual)-_pv_number(expected))
    return field


def _pv_one(candidates):
    return candidates[0] if len(candidates) == 1 else None


def _pv_rows_compare(actual_rows, baseline):
    expected_rows = baseline['items']
    out = []
    # This workflow creates exactly one item. Never hide extra printed rows.
    count = len(actual_rows)
    out.append({'field': 'items.row_count', 'key': 'row_count', 'expected': str(len(expected_rows)),
                'actual': str(count), 'status': 'PASS' if count == len(expected_rows) else ('UNMAPPED' if count == 0 else 'FAIL'),
                'reason': 'All detected item rows must belong to this single-item transaction.', 'page': None, 'bbox': None})
    if len(expected_rows) != 1:
        out.append({'field': 'items.mapping', 'key': 'mapping', 'expected': 'One item in the supplied workflow',
                    'actual': str(len(expected_rows)), 'status': 'UNMAPPED', 'reason': 'Configure multi-item row mapping before enabling multiple items.'})
        return out
    row = actual_rows[0] if count == 1 else {}
    expected = dict(expected_rows[0])
    screen = baseline['screen_items'][0]
    if row.get('item') and not row.get('item_code') and not row.get('item_name'):
        for key, value in _pv_split_item(row['item']['text']).items():
            row[key] = {**row['item'], 'text': value}
    # Printed quantity in a GRN row is treated as received quantity only if no
    # explicitly labeled received quantity exists. Reference Qty is never used.
    qty_key = 'received_qty' if baseline['document_type'] == 'GRN' else 'quantity'
    if qty_key == 'received_qty' and not row.get('received_qty') and row.get('quantity'):
        row['received_qty'] = row['quantity']
    # Validate amounts/percentages only when printed as line columns. Totals
    # below the table are mandatory separately for LPO.
    optional_line = {'discount_percentage', 'tax_percentage', 'gross', 'discount_amount', 'tax_amount', 'net', 'charges'}
    for key in list(expected):
        if key in optional_line and key not in row:
            expected.pop(key)
    # If the print contains a value that creation did not supply, report that gap.
    for key in _PV_NUMERIC - {'reference_qty', 'quantity' if qty_key=='received_qty' else 'received_qty'}:
        if row.get(key, {}).get('text') and key not in expected:
            expected[key] = None
    if row.get('uom', {}).get('text') and 'uom' not in expected:
        expected['uom'] = None
    for key, value in expected.items():
        must_capture = baseline['document_type'] == 'LPO' and key in ('quantity', 'unit_price', 'discount_percentage', 'gross', 'discount_amount', 'tax_amount', 'net')
        out.append(_pv_field(key, value, row.get(key), group='item[1]',
                             screen=screen.get(key), screen_required=must_capture))
    return out


def _pv_overall(fields):
    if any(f['status'] == 'FAIL' for f in fields):
        return 'FAIL'
    return 'PASS' if fields and all(f['status'] == 'PASS' for f in fields) else 'UNMAPPED'


def _pv_html(path, results):
    import html
    esc = lambda v: html.escape('' if v is None else str(v))
    body = []
    for r in results:
        body.append('<section><h2>' + esc(r.get('action')) + '</h2><p><strong>' + esc(r.get('status'))
                    + '</strong> | ' + esc(r.get('document_type')) + '</p>')
        if r.get('message'):
            body.append('<p>' + esc(r['message']) + '</p>')
        body.append('<div class="table"><table><thead><tr><th>Field</th><th>Expected</th><th>Creation screen</th><th>Printed</th><th>Result</th><th>Explanation</th></tr></thead><tbody>')
        for f in r.get('fields', []):
            cls = 'pass' if f['status']=='PASS' else 'fail' if f['status']=='FAIL' else 'review'
            body.append('<tr class="'+cls+'">' + ''.join('<td>'+esc(x)+'</td>' for x in
                (f['field'],f.get('expected'),f.get('creation_screen'),f.get('actual'),f['status'],f.get('reason'))) + '</tr>')
        body.append('</tbody></table></div></section>')
    text = '''<!doctype html><html><head><meta charset="utf-8"><title>Creation vs Print Validation</title><style>
body{margin:0;background:#f3f6fb;color:#15304e;font:15px/1.5 Arial,sans-serif}main{max-width:1400px;margin:auto;padding:28px}h1{margin-bottom:4px}section{background:white;border:1px solid #d7e1ee;border-radius:10px;margin-top:24px;padding:20px}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:10px;border:1px solid #d7e1ee;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#112f50;color:white}.pass td:nth-child(5){color:#176b36;font-weight:bold}.fail{background:#fff0f0}.fail td:nth-child(5){color:#ad1730;font-weight:bold}.review td:nth-child(5){color:#8b5c00;font-weight:bold}</style></head><body><main><h1>Creation vs Print Validation</h1><p>Exact item identity and numeric values. Missing or ambiguous evidence is not a PASS. Screen values remain separate from calculated expectations.</p>'''
    Path(path).write_text(text + ''.join(body) + '</main></body></html>', encoding='utf-8')


def validate_erp_print_pdf(pdf_path, document_type, expected, label):
    """Strict comparison against frozen creation values and labeled PDF cells."""
    import hashlib
    import uuid
    base = {'action': label, 'document_type': document_type, 'pdf': str(pdf_path), 'fields': []}
    try:
        import pymupdf as fitz
    except ImportError:
        return {**base, 'status': 'NOT_CONFIGURED', 'message': 'PyMuPDF is required; install it in the project virtual environment.'}
    if document_type not in PRINT_HEADER_ALIASES:
        return {**base, 'status': 'NOT_CONFIGURED', 'message': 'Unsupported document type: ' + str(document_type)}
    baseline = _pv_baseline(document_type, _pv_copy(expected))
    PRINT_REPORTS.mkdir(parents=True, exist_ok=True)
    baseline_bytes = json.dumps(baseline, sort_keys=True, indent=2).encode('utf-8')
    digest = hashlib.sha256(baseline_bytes).hexdigest()
    baseline_file = PRINT_REPORTS / ('creation_' + print_safe_name(baseline['header'].get('transaction')) + '_' + digest[:12] + '.json')
    if not baseline_file.exists():
        baseline_file.write_bytes(baseline_bytes)
    stem = print_safe_name(label) + '_' + uuid.uuid4().hex[:10]
    base.update(creation_snapshot=str(baseline_file), creation_sha256=digest)
    try:
        pdf = fitz.open(pdf_path)
    except Exception as exc:
        return {**base, 'status': 'NOT_READABLE', 'message': 'Cannot open captured PDF: ' + str(exc)}
    with pdf:
        if pdf.is_encrypted or len(pdf) > PRINT_MAX_PAGES:
            return {**base, 'status': 'NOT_READABLE', 'message': 'Encrypted PDF or page safety limit exceeded.'}
        rows, pages, regions = _pv_extract(pdf)
        if not any(pages):
            return {**base, 'status': 'NOT_READABLE', 'message': 'No extractable text in PDF. Scanned/image-only prints are not verified; no automatic OCR.'}
        fields = []
        for key, value in baseline['header'].items():
            candidates = []
            for i, words in enumerate(pages):
                candidates.extend(_pv_label_candidates(words, PRINT_HEADER_ALIASES[document_type][key], i, regions[i]))
            fields.append(_pv_field(key, value, _pv_one(candidates), group='document',
                         reason=('Expected exactly one labeled value; found '+str(len(candidates))) if len(candidates)!=1 else None))
        fields.extend(_pv_rows_compare(rows, baseline))
        totals = dict(baseline['totals'])
        for key, aliases in PRINT_TOTAL_ALIASES.items():
            candidates = []
            for i, words in enumerate(pages):
                floor = max((b[3] for b in regions[i]), default=None)
                candidates.extend(_pv_label_candidates(words, aliases, i, regions[i], numeric=True, table_floor=floor))
            # Validate every printed recognized total; never derive expected data from print.
            if key in totals or candidates:
                fields.append(_pv_field(key, totals.get(key), _pv_one(candidates), group='totals',
                              screen=baseline['screen_totals'].get(key), screen_required=document_type=='LPO',
                              reason=('Expected exactly one summary value; found '+str(len(candidates))) if len(candidates)!=1 else None))
        status = _pv_overall(fields)
        for f in fields:
            if f.get('page') and f.get('bbox'):
                color = (0.04,0.60,0.20) if f['status']=='PASS' else (0.85,0.04,0.10) if f['status']=='FAIL' else (0.85,0.54,0.02)
                rect = fitz.Rect(f['bbox']) + (-2,-2,2,2)
                page = pdf[f['page']-1]
                page.draw_rect(rect, color=color, width=1.6, overlay=True)
        output = PRINT_REPORTS / (stem + '_ANNOTATED.pdf')
        pdf.save(output, garbage=3, deflate=True)
        screenshots = []
        if status == 'FAIL':
            failed_pages = sorted({f['page'] for f in fields if f['status']=='FAIL' and f.get('page')})
            for no in failed_pages or [1]:
                image = PRINT_REPORTS / (stem + f'_page_{no}_FAIL.png')
                pdf[no-1].get_pixmap(matrix=fitz.Matrix(1.5,1.5), alpha=False).save(image)
                screenshots.append(str(image))
    result = {**base, 'status': status, 'fields': fields, 'annotated_pdf': str(output),
              'screenshots': screenshots, 'mismatches': [f for f in fields if f['status']=='FAIL'],
              'unmapped': [f for f in fields if f['status'] not in ('PASS','FAIL')],
              'message': 'Single-item workflow; numeric formatting differences are allowed, value differences are not.'}
    report = PRINT_REPORTS / (stem + '_comparison.html')
    _pv_html(report, [result])
    result['comparison_html'] = str(report)
    json_path = PRINT_REPORTS / (stem + '_comparison.json')
    result['comparison_json'] = str(json_path)
    json_path.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
    for f in fields:
        print('PRINT', f['status'], '|', f['field'], '| Creation:', f.get('creation_screen'),
              '| Expected:', f.get('expected'), '| Printed:', f.get('actual'))
    return result


class ERPPrintMonitor:
    """Capture fresh PDFs per action and compare to immutable creation baselines."""

    def __init__(self, context, page):
        self.context = context
        self.page = page
        self.documents = []
        self.results = []
        self.counter = 0
        self.last_viewers = []
        self.has_failures = False
        self._window_start = 0
        self._embedded_before = set()
        self._watched = set()
        self._by_digest = {}
        PRINT_REPORTS.mkdir(parents=True, exist_ok=True)
        context.on('response', self._on_response)
        context.on('page', self._watch_page)
        for active in context.pages:
            self._watch_page(active)

    def _watch_page(self, page):
        if id(page) not in self._watched:
            page.on('download', self._on_download)
            self._watched.add(id(page))

    def _viewer_urls(self):
        found = set()
        for page in self.context.pages:
            try:
                urls = page.evaluate('''() => Array.from(document.querySelectorAll('iframe,embed,object'))
                  .map(el => el.getAttribute('src') || el.getAttribute('data') || '')
                  .filter(Boolean)''')
                found.update('embedded:' + u for u in urls)
            except Exception:
                pass
        return found

    def _capture_embedded_pdf(self):
        import base64
        script = r'''async () => {
          const viewers = Array.from(document.querySelectorAll('iframe,embed,object')).map(el => {
            const r = el.getBoundingClientRect();
            return {url:el.getAttribute('src') || el.getAttribute('data') || '',
                    type:el.getAttribute('type') || '', visible:r.width>10 && r.height>10};
          }).filter(x => x.visible && x.url);
          const results=[];
          for (const v of viewers) {
            if (!/^(blob:|data:application\/pdf)|\.pdf(?:[?#]|$)|\/pdf\b/i.test(v.url)
                && v.type !== 'application/pdf') continue;
            if (/^(chrome-extension:|about:)/i.test(v.url)) continue;
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 5000);
            try {
              const res=await fetch(v.url,{credentials:'include',signal:controller.signal});
              if(!res.ok) throw Error('PDF fetch HTTP '+res.status);
              const blob=await res.blob();
              if(blob.size>15000000) throw Error('PDF size limit');
              const data=await new Promise((resolve,reject)=>{
                const rd=new FileReader();rd.onload=()=>resolve(String(rd.result).split(',')[1]);
                rd.onerror=reject;rd.readAsDataURL(blob);
              });results.push({url:v.url,data});
            }catch(e){results.push({url:v.url,error:String(e)})}finally{clearTimeout(timer)}
          }
          return {viewers,results};
        }'''
        self.last_viewers = []
        for active in self.context.pages:
            try:
                output = active.evaluate(script)
                self.last_viewers.extend(output.get('viewers', []))
                for entry in output.get('results', []):
                    if entry.get('data'):
                        self._store(base64.b64decode(entry['data']), 'embedded:' + entry['url'])
                    elif entry.get('error'):
                        print('PRINT CAPTURE REVIEW:', entry['error'])
            except Exception as exc:
                print('PRINT CAPTURE REVIEW:', str(exc)[:180])

    def _store(self, content, origin):
        import hashlib
        if not print_is_pdf(content) or len(content) > PRINT_CAPTURE_MAX_BYTES:
            return
        # An old still-visible viewer is not evidence that the current action printed.
        if origin.startswith('embedded:') and origin in self._embedded_before:
            return
        digest = hashlib.sha256(content).hexdigest()
        if any(x['sha256']==digest for x in self.documents[self._window_start:]):
            return
        path = self._by_digest.get(digest)
        if path is None:
            self.counter += 1
            path = PRINT_REPORTS / f'captured_{self.counter:03d}_{digest[:10]}.pdf'
            path.write_bytes(content)
            self._by_digest[digest] = path
        # Reprinting identical bytes in a NEW action is still a new capture event.
        self.documents.append({'path':str(path), 'origin':origin, 'sha256':digest})
        print('PRINT PDF CAPTURED:', path.name)

    def _on_response(self, response):
        try:
            h = response.headers
            kind = h.get('content-type', '').lower()
            name = h.get('content-disposition', '').lower()
            if 'pdf' not in kind and 'pdf' not in name and not response.url.lower().split('?')[0].endswith('.pdf'):
                return
            length = h.get('content-length', '')
            if length.isdigit() and int(length) > PRINT_CAPTURE_MAX_BYTES:
                return
            self._store(response.body(), 'network-response')
        except Exception as exc:
            print('PRINT CAPTURE REVIEW:', str(exc)[:180])

    def _on_download(self, download):
        try:
            if not download.suggested_filename.lower().endswith('.pdf'):
                return
            p = Path(download.path())
            if p.stat().st_size <= PRINT_CAPTURE_MAX_BYTES:
                self._store(p.read_bytes(), 'browser-download')
        except Exception as exc:
            print('PRINT CAPTURE REVIEW:', str(exc)[:180])

    def checkpoint(self):
        self._embedded_before = self._viewer_urls()
        self._window_start = len(self.documents)
        return self._window_start

    def _emit_result(self, result):
        artifact = result.get('comparison_html') or result.get('annotated_pdf')
        relative = None
        if artifact and run_directory():
            try:
                relative = Path(artifact).relative_to(run_directory()).as_posix()
            except ValueError:
                pass
        fields = result.get('fields', [])
        for f in fields:
            emit('check', name=f"Print {result['document_type']}: {f['field']}",
                 status={'PASS':'PASSED','FAIL':'FAILED'}.get(f['status'],'REVIEW'),
                 expected=str(f.get('expected')),
                 actual=f"Creation screen={f.get('creation_screen')}; Printed={f.get('actual')}; {f.get('reason','')}",
                 process='Creation vs PDF print', category='Print validation', evidence=relative)
        # No fields (e.g. no captured print) must still be visible as REVIEW/FAIL.
        if not fields:
            emit('print_check', name=result.get('action'), status=result.get('status','REVIEW'),
                 expected='Capture and verify the actual print for this transaction',
                 actual=result.get('message','No verifiable fields'), process='Creation vs PDF print',
                 category='Print validation', evidence=relative, fields=[])
        else:
            emit('print_validation_summary', name=result.get('action'), status=result['status'],
                 fields=fields, evidence=relative, process='Creation vs PDF print')

    def validate_new(self, start, doc_type, expected, label):
        # Copy now. Future approval roles must not mutate creation expectations.
        expected = _pv_copy(expected)
        self.page.wait_for_timeout(PRINT_CAPTURE_WAIT_MS)
        self._capture_embedded_pdf()
        new_docs = self.documents[start:]
        if not new_docs:
            result = {'action':label, 'document_type':doc_type, 'fields':[],
                      'status':'FAIL_NO_PDF' if PRINT_REQUIRE_PDF else 'NOT_CAPTURED',
                      'message':'No fresh PDF was captured for this action. No printed values have been verified.'}
            self.results.append(result)
            self.has_failures |= PRINT_REQUIRE_PDF
            self._emit_result(result)
            self.save_report()
            if PRINT_REQUIRE_PDF:
                raise AssertionError('Required PDF not captured after ' + label)
            return result
        found = []
        for entry in new_docs:
            result = validate_erp_print_pdf(entry['path'], doc_type, expected, label)
            self.results.append(result)
            found.append(result)
            self.has_failures |= result['status'] == 'FAIL'
            self._emit_result(result)
            print_show_failure_on_current_page(self.page, label, result)
            self.show_annotated_preview(result, label)
        self.save_report()
        if PRINT_STOP_ON_MISMATCH and any(r['status']=='FAIL' for r in found):
            raise AssertionError('Printed document differs from creation: ' + label)
        # Do not return a later PASS over an earlier failed or unverified capture.
        return next((r for r in found if r['status']=='FAIL'),
                    next((r for r in found if r['status']!='PASS'), found[-1]))

    def save_report(self):
        PRINT_REPORTS.mkdir(parents=True, exist_ok=True)
        json_path = PRINT_REPORTS / 'print_validation_report.json'
        json_path.write_text(json.dumps(self.results, indent=2, default=str), encoding='utf-8')
        _pv_html(PRINT_REPORTS / 'print_validation_report.html', self.results)
        print('PRINT VALIDATION REPORT:', json_path)

    def show_annotated_preview(self, result, label):
        """Display annotated PDF pages in a temporary Chromium tab, then resume ERP.

        Chrome's existing embedded PDF viewer cannot be edited in place.
        Rendering the *annotated* PDF in a new tab shows exactly the green/red
        boxes generated by the validator, without changing the ERP document.
        """
        if not PRINT_PREVIEW_ENABLED:
            return
        pdf_path = result.get("annotated_pdf")
        if not pdf_path or not Path(pdf_path).is_file():
            return
        preview = None
        try:
            import base64
            import html
            import pymupdf
            image_tags = []
            with pymupdf.open(pdf_path) as doc:
                for n, pdf_page in enumerate(doc):
                    png = pdf_page.get_pixmap(
                        matrix=pymupdf.Matrix(1.5, 1.5), alpha=False
                    ).tobytes("png")
                    image_data = base64.b64encode(png).decode("ascii")
                    image_tags.append(
                        f'<figure><figcaption>Page {n + 1}</figcaption>'
                        f'<img alt="Annotated PDF page {n + 1}" '
                        f'src="data:image/png;base64,{image_data}"></figure>'
                    )
            status = html.escape(result.get("status", "UNKNOWN"))
            safe_label = html.escape(label)
            preview = self.context.new_page()
            preview.set_content("""<!doctype html><html><head><meta charset="utf-8">
            <title>ERP Print Validation</title><style>
            body{margin:0;background:#e8ecf0;font:16px Arial,sans-serif;color:#182b35}
            header{position:sticky;top:0;background:#122d41;color:#fff;
              padding:12px 20px;z-index:5;box-shadow:0 2px 7px #0002}
            .status{font-weight:bold;margin-left:20px}
            figure{margin:22px auto;max-width:1050px;text-align:center}
            figcaption{padding:8px}
            img{max-width:100%;height:auto;background:white;box-shadow:0 3px 12px #0003}
            </style></head><body><header><strong>ERP PDF PRINT VALIDATION</strong>
            <span class="status">{status}</span><div>{safe_label}</div>
            <small>Green = matched printed field. Red = discrepancy. Preview closes automatically.</small>
            </header>__PAGES__</body></html>"""
                .replace("{status}", status)
                .replace("{safe_label}", safe_label)
                .replace("__PAGES__", "".join(image_tags)), wait_until="load")
            preview.bring_to_front()
            # Capture the rendered ERP print document with the REAL red/green
            # boxes drawn onto the copied PDF, not the plain ERP page underneath.
            if result.get('status') == 'FAIL':
                preview_file = PRINT_REPORTS / (print_safe_name(label) + '_ANNOTATED_PRINT_SCREEN.png')
                preview.screenshot(path=str(preview_file), full_page=True)
                result['annotated_print_screen'] = str(preview_file)
                print('ANNOTATED PRINT SCREENSHOT:', preview_file)
            print(f"PRINT PREVIEW DISPLAYED ({status}): {pdf_path}")
            preview.wait_for_timeout(PRINT_PREVIEW_DURATION_MS)
        except Exception as error:
            print("PRINT PREVIEW UNAVAILABLE:", str(error)[:250])
        finally:
            if preview is not None:
                try:
                    preview.close()
                except Exception:
                    pass
            try:
                self.page.bring_to_front()
            except Exception:
                pass


def print_show_failure_on_current_page(page, label, result):
    """Red failure box in the current ERP page, then capture evidence."""
    if result.get("status") != "FAIL":
        return
    messages = [f"PRINT VALIDATION FAILED: {label}"]
    for m in result.get("mismatches", []):
        messages.append(f"{m['field']}: Expected {m['expected']} | {m['actual']}")
    try:
        page.evaluate("""messages => {
            document.getElementById('qa-print-failure')?.remove();
            const box=document.createElement('div');
            box.id='qa-print-failure';
            box.style.cssText='position:fixed;left:20px;top:20px;max-width:85vw;z-index:2147483647;background:#fff4f4;color:#a00000;border:4px solid red;padding:16px;font:600 14px Arial;white-space:pre-wrap;box-shadow:0 4px 20px #4447';
            box.textContent=messages.join('\\n');document.body.appendChild(box);
        }""", messages)
        path = PRINT_REPORTS / (print_safe_name(label) + '_SAME_PAGE_FAIL.png')
        page.screenshot(path=str(path), full_page=False)
        result['same_page_screenshot'] = str(path)
        print('PRINT SAME-PAGE RED BOX EVIDENCE:', path)
    except Exception as err:
        print('Unable to mark ERP page:', err)
    finally:
        try:
            page.evaluate("document.getElementById('qa-print-failure')?.remove()")
        except Exception:
            pass


def monitor_print_action(monitor, doc_type, expected, label, action):
    """Run the user's original ERP operation, then check its generated PDF."""
    checkpoint = monitor.checkpoint()
    outcome = action()
    monitor.validate_new(checkpoint, doc_type, expected, label)
    return outcome





@stage('Goods Receipt Note: create and save', 'Same LPO and vendor are used, warehouse quantity checked, new GRN identified', verified=True)
def save_grn_from_lpo(page, pi, lpo):
    """Reference -> existing item -> existing warehouse qty -> OK -> OK -> SAVE."""
    number = lpo['transaction']
    print('Using PO vendor:', lpo.get('vendor'))
    print('Using exact PO transaction:', number)
    log(f'GRN CREATE FOR APPROVED LPO: {number}')
    global_search(page, 'Goods Receipt Note', 'Goods Receipt Note')
    # GRN landing page may not render an AG Grid. Wait for CREATE itself.
    create = page.get_by_role('button', name=re.compile(r'^\s*CREATE\s*$', re.I)).and_(page.locator(':visible'))
    try:
        expect(create).to_have_count(1, timeout=TIMEOUT)
        expect(create).to_be_enabled(timeout=TIMEOUT)
    except Exception:
        visible_buttons = page.get_by_role('button').and_(page.locator(':visible')).all_inner_texts()
        raise RuntimeError(
            f'GRN landing page opened, but CREATE was not uniquely available. '
            f'Visible buttons: {visible_buttons[:30]!r}, URL: {page.url}'
        )
    # Snapshot existing records only when the GRN list uses AG Grid.
    has_grn_grid = page.locator('.ag-root:visible').count() > 0
    before = {r['text'] for r in grid_rows(page)} if has_grn_grid else None
    create.click()
    print('PASS: Goods Receipt Note CREATE clicked')

    reference = grn_field(page, 'grnreferenceId')
    expect(reference).to_be_visible(timeout=TIMEOUT)
    grn_select_matching(page, reference, 'Local PO')
    print('PASS: GRN Reference = Local PO')

    # Select the vendor saved on the SAME approved Local PO first.
    vendor_name = str(lpo.get('vendor') or '').strip()
    if not vendor_name:
        raise RuntimeError('Approved Local PO has no vendor; refusing to select a different vendor')
    vendor = grn_field(page, 'vendorId')
    expect(vendor).to_be_visible(timeout=TIMEOUT)
    grn_select_po_vendor(page, vendor, vendor_name)
    print('PASS: Selected approved PO vendor:', vendor_name)

    # Select only the same PO, not a similarly numbered PO.
    po = grn_field(page, 'localPOId')
    expect(po).to_be_visible(timeout=TIMEOUT)
    grn_select_exact_po(page, po, number)
    shown_po = po.input_value() if po.evaluate('(el) => el.tagName') == 'INPUT' else po.inner_text()
    if number.casefold() not in shown_po.casefold():
        raise RuntimeError(f'Wrong GRN Local PO: expected {number!r}, got {shown_po!r}')
    print('PASS: Selected matching PO transaction:', number)

    # The ERP automatically populates the linked item, UOM, price,
    # tax definition and warehouse row after the Local PO selection.
    expect(vendor).to_be_visible(timeout=TIMEOUT)
    # Invoice No: a random four-digit number, not the PO transaction.
    invoice_no = str(random.randint(1000, 9999))
    invoice_field = grn_field(page, 'vendorRefDocno')
    expect(invoice_field).to_be_visible(timeout=TIMEOUT)
    expect(invoice_field).to_be_enabled(timeout=TIMEOUT)
    if invoice_field.get_attribute('readonly') is not None:
        raise RuntimeError('Invoice No is read-only; cannot enter a generated number')
    invoice_field.fill(invoice_no)
    expect(invoice_field).to_have_value(invoice_no, timeout=TIMEOUT)
    invoice_field.press('Tab')
    print('PASS: Random four-digit GRN Invoice No:', invoice_no)
    page._grn_invoice_no = invoice_no

    # Stable, captured GRN completion flow.
    return finish_grn_from_invoice_date(page, pi, lpo, before)


GRN_NUMBER_RE = re.compile(
    r'\b(?:LEO/)?GRN/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)+\b', re.I
)


GRN_OK_TEXT = re.compile(r'^\s*ok\s*$', re.IGNORECASE)


def grn_ui_feedback(page):
    """Expose a visible ERP validation message if an action is blocked."""
    selectors = (
        '[role="alert"]:visible, '
        '.MuiFormHelperText-root:visible, '
        '.MuiAlert-message:visible, '
        '[aria-invalid="true"]:visible'
    )
    issues = []
    for node in page.locator(selectors).all():
        try:
            message = node.inner_text().strip()
            if message and message not in issues:
                issues.append(message)
        except Exception:
            continue
    return issues[:12]


def grn_exact_visible_button(page, name):
    """Select exactly one enabled visible SAVE/SUBMIT button; ignore case."""
    pattern = re.compile(r'^\s*' + re.escape(name) + r'\s*$', re.I)
    buttons = page.get_by_role('button', name=pattern).and_(page.locator(':visible'))
    try:
        expect(buttons).to_have_count(1, timeout=TIMEOUT)
        expect(buttons).to_be_enabled(timeout=TIMEOUT)
    except Exception as exc:
        labels = page.get_by_role('button').and_(page.locator(':visible')).all_inner_texts()
        raise RuntimeError(
            f'{name} button is missing, disabled, or ambiguous; '
            f'matches={buttons.count()}, visible buttons={labels[:25]!r}, '
            f'ERP messages={grn_ui_feedback(page)!r}'
        ) from exc
    return buttons



def select_grn_invoice_date(page):
    """Choose today's IST date without a generated React input ID."""
    today = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    target = today.strftime('%d/%m/%Y')

    # The capture contains two dd/mm/yyyy fields, so scope by LABEL.
    label = page.get_by_text(
        re.compile(r'^\s*Invoice Date\s*\*?\s*$', re.I)
    ).and_(
        page.locator(':visible')
    )
    expect(label).to_have_count(1, timeout=TIMEOUT)
    field = label.locator(
        'xpath=ancestor::div[.//input[@placeholder="dd/mm/yyyy"]][1]'
        '//input[@placeholder="dd/mm/yyyy"]'
    )
    expect(field).to_have_count(1, timeout=TIMEOUT)
    expect(field).to_be_visible(timeout=TIMEOUT)

    if field.input_value().strip() == target:
        print('PASS - Invoice Date already set:', target)
        return target

    # Read-only MUI date fields must be selected from the calendar.
    field.click()
    calendar = page.locator(
        '.MuiDateCalendar-root:visible, .MuiCalendarPicker-root:visible'
    )
    try:
        calendar.first.wait_for(state='visible', timeout=2000)
    except Exception:
        # Some ERP themes require clicking the calendar icon.
        wrapper = field.locator(
            'xpath=ancestor::div[contains(@class,"MuiInputBase-root")][1]'
        )
        icon = wrapper.locator(
            'svg[data-testid="CalendarMonthOutlinedIcon"], '
            'svg[data-testid="CalendarMonthIcon"], '
            'svg[data-testid="CalendarTodayIcon"]'
        )
        expect(icon).to_have_count(1, timeout=TIMEOUT)
        icon.click()

    expect(calendar).to_have_count(1, timeout=TIMEOUT)
    header = calendar.locator('.MuiPickersCalendarHeader-label')
    expect(header).to_have_count(1, timeout=TIMEOUT)

    for _ in range(36):
        shown = header.inner_text().strip()
        if shown == today.strftime('%B %Y'):
            break
        try:
            month = datetime.strptime(shown, '%B %Y')
        except ValueError as exc:
            raise RuntimeError('Unexpected calendar month header: ' + shown) from exc

        direction = (
            'Next month' if (month.year, month.month) < (today.year, today.month)
            else 'Previous month'
        )
        arrow = calendar.get_by_role('button', name=direction, exact=True)
        expect(arrow).to_have_count(1, timeout=TIMEOUT)
        arrow.click()
        expect(header).not_to_have_text(shown, timeout=TIMEOUT)
    else:
        raise RuntimeError('Invoice calendar did not reach the current IST month')

    day = calendar.locator(
        'button.MuiPickersDay-root:not(.MuiPickersDay-dayOutsideMonth):visible'
    ).filter(has_text=re.compile(r'^\s*' + str(today.day) + r'\s*$'))
    expect(day).to_have_count(1, timeout=TIMEOUT)
    day.click()
    expect(field).to_have_value(target, timeout=TIMEOUT)
    print('PASS - Invoice Date:', target)
    return target


def grn_edit_buttons(scope):
    """Prefer the Edit row accessible name/title over numeric cell IDs."""
    buttons = scope.locator(
        'button[title="Edit row"]:visible, '
        'button[aria-label="Edit row"]:visible'
    )
    if buttons.count() == 0:
        buttons = scope.get_by_role('button', name='Edit row', exact=True).and_(
            scope.locator(':visible')
        )
    return buttons


def grn_click_item_edit(page):
    # The capture shows the GRN Item Details grid under simple-tabpanel-0.
    # Use the semantic tab panel and Reference Qty header first.
    panels = page.get_by_role('tabpanel').filter(
        has=page.get_by_text('Reference Qty', exact=True)
    )
    if panels.count() != 1:
        panels = page.locator('#simple-tabpanel-0:visible')
    expect(panels).to_have_count(1, timeout=TIMEOUT)
    buttons = grn_edit_buttons(panels)
    if buttons.count() != 1:
        raise RuntimeError(
            'GRN Item Details must have exactly one editable item row; '
            f'found {buttons.count()}. No row was changed.'
        )
    buttons.click()
    expect(page.get_by_text('Edit GRN Item Details', exact=True)).to_be_visible(
        timeout=TIMEOUT
    )
    print('PASS - Opened GRN item editor')


def grn_click_warehouse_edit(page):
    # The captured Warehouse Details header has a stable ID.
    heading = page.locator('[id="Whdetails_216"]:visible')
    expect(heading).to_have_count(1, timeout=TIMEOUT)
    section = heading.locator(
        'xpath=ancestor::*['
        './/button[@title="Edit row" or @aria-label="Edit row"]'
        '][1]'
    )
    expect(section).to_have_count(1, timeout=TIMEOUT)
    buttons = grn_edit_buttons(section)
    if buttons.count() != 1:
        raise RuntimeError(
            'Warehouse Details must have exactly one editable row; '
            f'found {buttons.count()}. No row was changed.'
        )
    buttons.click()
    expect(page.get_by_text('Edit Warehouse Details', exact=True)).to_be_visible(
        timeout=TIMEOUT
    )
    print('PASS - Opened Warehouse Details editor')


def grn_modal_ok(page, title):
    """Click ONLY the OK of the requested editor (supports actual lowercase 'ok')."""
    title_rx = re.compile(r'^\s*' + re.escape(title) + r'\s*$', re.I)
    heading = page.get_by_text(title_rx).and_(page.locator(':visible'))
    expect(heading).to_have_count(1, timeout=TIMEOUT)

    # Find nearest ancestor of the title with a descendant OK button.
    # The button is '<button ...>ok<span ...></span></button>' on this ERP.
    # This XPath searches case-insensitively and does not use changing jss IDs.
    wrapper = heading.locator(
        'xpath=ancestor::*[.//button['
        'translate(normalize-space(.),'
        '"ABCDEFGHIJKLMNOPQRSTUVWXYZ",'
        '"abcdefghijklmnopqrstuvwxyz")="ok"]][1]'
    )
    ok = None
    if wrapper.count() == 1:
        candidate = wrapper.get_by_role('button', name=GRN_OK_TEXT).and_(
            wrapper.locator(':visible')
        )
        if candidate.count() == 1:
            ok = candidate

    # If React rendered the footer separately, use this editor's role=dialog.
    if ok is None:
        dialog = heading.locator('xpath=ancestor::*[@role="dialog"][1]')
        if dialog.count() == 1:
            candidate = dialog.get_by_role('button', name=GRN_OK_TEXT).and_(
                dialog.locator(':visible')
            )
            if candidate.count() == 1:
                ok = candidate

    # Last safe fallback: exactly one clickable OK in the whole page.
    # With two editors open, the parent OK is usually obscured by the child.
    if ok is None:
        candidates = page.locator('button.MuiButton-root:visible').filter(
            has_text=GRN_OK_TEXT
        )
        viable = []
        for i in range(candidates.count()):
            button = candidates.nth(i)
            try:
                button.click(trial=True, timeout=1200)
                viable.append(i)
            except Exception:
                pass
        if len(viable) == 1:
            ok = candidates.nth(viable[0])

    if ok is None:
        details = page.locator('button.MuiButton-root:visible').filter(
            has_text=GRN_OK_TEXT
        ).count()
        raise RuntimeError(
            f'Cannot uniquely identify {title!r} OK (visible OK buttons={details}). '
            f'ERP messages: {grn_ui_feedback(page)!r}. Stopping without guessing.'
        )

    expect(ok).to_be_enabled(timeout=TIMEOUT)
    ok.click(timeout=TIMEOUT)
    try:
        expect(heading).to_be_hidden(timeout=TIMEOUT)
    except Exception as exc:
        raise RuntimeError(
            f'Clicked {title!r} OK, but editor remained open. '
            f'ERP validation messages: {grn_ui_feedback(page)!r}'
        ) from exc
    print(f'PASS: {title} -> ok clicked and editor closed')



def grn_numbers(text):
    return {m.group(0) for m in GRN_NUMBER_RE.finditer(text)}


def find_new_grn(page, existing_row_texts):
    """Only accept a uniquely new, ERP-generated transaction."""
    previous_numbers = set()
    for text in existing_row_texts:
        previous_numbers.update(grn_numbers(text))

    page.locator('.ag-root:visible').first.wait_for(
        state='visible', timeout=TIMEOUT
    )
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        newly_seen = set()
        for row in grid_rows(page):
            newly_seen.update(grn_numbers(row['text']) - previous_numbers)
        if len(newly_seen) == 1:
            new_number = next(iter(newly_seen))
            print('PASS - Saved new GRN:', new_number)
            return new_number
        if len(newly_seen) > 1:
            raise RuntimeError(
                f'Multiple newly visible GRNs {sorted(newly_seen)}; '
                'will not guess which one to submit.'
            )
        page.wait_for_timeout(600)
    raise RuntimeError(
        'SAVE may have been clicked, but no unique new GRN was found. '
        'Check ERP before attempting SAVE or SUBMIT again.'
    )


def finish_grn_from_invoice_date(page, pi, lpo, before):
    """Called after vendor, PO and invoice number are already selected."""
    if before is None:
        raise RuntimeError(
            'GRN list snapshot was unavailable before CREATE. '
            'Cannot safely identify the document after SAVE.'
        )

    po_number = str(lpo['transaction']).strip()
    if not po_number:
        raise RuntimeError('Expected approved PO transaction is blank')

    page._grn_invoice_date = select_grn_invoice_date(page)

    description = 'Receipt for approved ' + po_number
    desc = grn_field(page, 'description')
    expect(desc).to_be_visible(timeout=TIMEOUT)
    expect(desc).to_be_enabled(timeout=TIMEOUT)
    if desc.get_attribute('readonly') is not None:
        raise RuntimeError('Description is read-only')
    desc.fill(description)
    desc.press('Tab')
    expect(desc).to_have_value(description, timeout=TIMEOUT)
    page._grn_description = description
    print('PASS - Description:', description)

    # One item in this workflow: edit existing row, do not add another.
    grn_click_item_edit(page)
    grn_click_warehouse_edit(page)

    received_qty = Decimal(str(lpo['quantity']))
    if not received_qty.is_finite() or received_qty <= 0:
        raise ValueError('Approved PO quantity must be positive and finite')
    qty = page.locator('[id="Whdetails_216.qty"]:visible')
    expect(qty).to_have_count(1, timeout=TIMEOUT)
    expect(qty).to_be_enabled(timeout=TIMEOUT)
    if qty.get_attribute('readonly') is not None:
        raise RuntimeError('Warehouse quantity is read-only')
    qty.fill(str(received_qty))
    qty.press('Tab')
    actual = Decimal(qty.input_value().replace(',', '').strip())
    if actual != received_qty:
        check('Goods Receipt Note: Warehouse Received Quantity', False, received_qty, actual,
              page=page, process='Goods Receipt Note')
        raise RuntimeError(
            f'Warehouse quantity changed: expected {received_qty}, got {actual}'
        )
    check('Goods Receipt Note: Warehouse Received Quantity', True, received_qty, actual,
          page=page, process='Goods Receipt Note')
    print('PASS - Warehouse quantity:', actual)

    # Two different OK buttons, one for each nested editor.
    grn_modal_ok(page, 'Edit Warehouse Details')
    capture_grn_print_item(page, actual)
    grn_modal_ok(page, 'Edit GRN Item Details')
    # Both editors must be dismissed before SAVE.
    expect(page.get_by_text('Edit Warehouse Details', exact=True)).to_be_hidden(timeout=TIMEOUT)
    expect(page.get_by_text('Edit GRN Item Details', exact=True)).to_be_hidden(timeout=TIMEOUT)

    # Recheck the approved vendor and exact approved PO before committing.
    vendor = grn_field(page, 'vendorId').input_value().strip()
    wanted_vendor = str(lpo.get('vendor') or '').strip()
    def vendor_name(text):
        text = re.sub(r'^\s*\d+\s*-\s*', '', text)
        text = re.sub(r'\s*-\s*\d+\s*$', '', text)
        return ' '.join(text.lower().split())
    if not wanted_vendor or vendor_name(vendor) != vendor_name(wanted_vendor):
        raise RuntimeError('Vendor does not match the approved LPO. SAVE blocked.')
    selected_po = grn_field(page, 'localPOId').input_value().strip()
    if not re.match(r'^\s*' + re.escape(po_number) + r'(?=\s*(?:-|$))', selected_po, re.I):
        raise RuntimeError('Selected GRN PO differs from approved LPO. SAVE blocked.')

    # SAVE exactly once. Never retry an unknown persistence outcome.
    capture_grn_print_summary(page)
    grn_exact_visible_button(page, 'SAVE').click()
    return find_new_grn(page, before)


@stage('Goods Receipt Note: submit', 'Submit is clicked for the exact saved GRN; final status needs an assertion', verified=False)
def submit_saved_grn(page, grn_number):
    """Submit only the exact saved transaction from the GRN list."""
    page.locator('.ag-root:visible').first.wait_for(
        state='visible', timeout=TIMEOUT
    )
    matches = []
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        matches.clear()
        for row in grid_rows(page):
            if grn_number in grn_numbers(row['text']):
                matches.append(row['index'])
        if len(matches) == 1:
            break
        if len(matches) > 1:
            raise RuntimeError('Duplicate GRN rows for ' + grn_number)
        page.wait_for_timeout(600)

    if len(matches) != 1:
        raise RuntimeError(
            'Exact saved GRN not found; no other record will be submitted: '
            + grn_number
        )

    select_grid_row(page, matches[0])
    grn_exact_visible_button(page, 'SUBMIT').click()
    print('SUBMIT clicked for exact GRN:', grn_number)
    print('Confirm status or approval trail in ERP for submission verification.')
    return 'SUBMIT_CLICKED_NOT_INDEPENDENTLY_VERIFIED'


def main():
    if not 1 <= TOTAL_RECORDS <= len(TEST_DATA):
        raise ValueError("TOTAL_RECORDS is outside TEST_DATA")

    results = []
    stop_button_process = None if run_directory() else start_emergency_stop_button()
    with sync_playwright() as p:
        browser, context, page, owns_browser = open_script_browser(p, ERP_URL, TIMEOUT)
        page.set_default_timeout(TIMEOUT)
        print_monitor = ERPPrintMonitor(context, page)
        trace_started = False
        if run_directory():
            try:
                context.tracing.start(screenshots=True, snapshots=True, sources=False)
                trace_started = True
            except Exception as exc:
                emit('trace_warning', message=str(exc)[:500])

        try:
            current_user = "DMG0013"
            if owns_browser:
                page.goto(ERP_URL, wait_until="domcontentloaded", timeout=60000)
                login(page, current_user)
            else:
                # Do NOT reload/login at startup. The tester explicitly confirms
                # the active account. The supplied approval flow still switches roles.
                expect(page.locator("div.pro-sidebar")).to_be_visible(timeout=TIMEOUT)
                if page.locator("#username").is_visible():
                    raise RuntimeError("The managed ERP session is not logged in")
                emit('session_reused', message='Existing page reused without navigation; initial role confirmed by tester')

            for record in TEST_DATA[:TOTAL_RECORDS]:
                # 1. DMG0013 creates and SUBMITS Purchase Indent.
                pi_pdf_checkpoint = print_monitor.checkpoint()
                pi = create_indent(page, record)
                print_monitor.validate_new(
                    pi_pdf_checkpoint, "PI",
                    pi,
                    "PI created and submitted " + pi["transaction"]
                )
                emit('erp_values', process='Purchase Indent', transaction=pi['transaction'],
                     values={key: pi.get(key) for key in ('transaction', 'kind', 'department', 'purchase', 'section', 'asset', 'date', 'item', 'uom', 'qty')},
                     note='Script-selected values; final ERP persistence and approval require independent validation')
                transaction = pi["transaction"]
                report = {
                    "record": record["name"],
                    "pi": transaction,
                    "creator": "DMG0013",
                    "pi_status": "SUBMIT_CLICKED_NOT_INDEPENDENTLY_VERIFIED",
                }
                results.append(report)

                # 2. SAME DMG0013 session: approve the EXACT saved PI.
                # After Submit, create_indent leaves the PI View page open.
                pi_pdf_checkpoint = print_monitor.checkpoint()
                report["DMG0013_approval"] = approve_indent(
                    page, transaction, "DMG0013", from_pi_view=True
                )
                print_monitor.validate_new(pi_pdf_checkpoint, "PI",
                    pi, "PI approval DMG0013 " + transaction)

                # 3. DMG0041: approve the SAME PI.
                logout(page, current_user)
                current_user = "DMG0041"
                login(page, current_user)
                pi_pdf_checkpoint = print_monitor.checkpoint()
                report["DMG0041_approval"] = approve_indent(
                    page, transaction, current_user
                )
                print_monitor.validate_new(pi_pdf_checkpoint, "PI",
                    pi, "PI approval DMG0041 " + transaction)

                # 4. DMG0051: approve the SAME PI.
                logout(page, current_user)
                current_user = "DMG0051"
                login(page, current_user)
                pi_pdf_checkpoint = print_monitor.checkpoint()
                report["DMG0051_approval"] = approve_indent(
                    page, transaction, current_user
                )
                print_monitor.validate_new(pi_pdf_checkpoint, "PI",
                    pi, "PI approval DMG0051 " + transaction)

                # 5. DMG0041: create LPO from EXACT PI transaction.
                logout(page, current_user)
                current_user = "DMG0041"
                login(page, current_user)
                lpo_pdf_checkpoint = print_monitor.checkpoint()
                report["lpo"] = create_lpo(page, pi)
                emit('erp_values', process='Local Purchase Order', transaction=report['lpo'].get('transaction'),
                     values={key: report['lpo'].get(key) for key in ('status', 'transaction', 'po_number', 'category', 'reference', 'department', 'vendor', 'payment_terms', 'item', 'quantity', 'unit_price', 'discount_percentage', 'tax_definition', 'narration')},
                     note='Captured from the LPO creation workflow; verify final saved/approved state separately')
                if report["lpo"]["status"] == "LPO_VALIDATION_FAILED_NOT_SAVED":
                    break

                # 6. Submit newly saved LPO with DMG0041.
                lpo_number = report["lpo"]["transaction"]
                lpo_expected = dict(report["lpo"])
                lpo_expected["transaction"] = lpo_number
                gross = money(decimal(lpo_expected["quantity"]) * decimal(lpo_expected["unit_price"]))
                discount_amount = money(gross * decimal(lpo_expected["discount_percentage"]) / Decimal("100"))
                tax_amount = money((gross - discount_amount) * TAX_RATE / Decimal("100"))
                lpo_expected.update(gross=gross, discount_amount=discount_amount,
                                    tax_amount=tax_amount, charges=EXPECTED_CHARGES,
                                    net=money(gross-discount_amount+tax_amount+EXPECTED_CHARGES))
                emit('erp_values', process='LPO Calculated Amounts', transaction=lpo_number,
                     values={key: str(lpo_expected.get(key)) for key in ('quantity','unit_price','discount_percentage','gross','discount_amount','tax_amount','net')},
                     note='Expected calculations from recorded LPO inputs; real displayed ERP values are separate instrumented checks')
                print_monitor.validate_new(lpo_pdf_checkpoint, "LPO", lpo_expected,
                    "LPO created " + lpo_number)
                report["lpo_submit"] = monitor_print_action(
                    print_monitor, "LPO", lpo_expected, "LPO submit " + lpo_number,
                    lambda: submit_lpo(page, lpo_number))

                # 7. DMG0041 first LPO approval, same session.
                report["lpo_approvals"] = {}
                report["lpo_approvals"]["DMG0041"] = monitor_print_action(
                    print_monitor, "LPO", lpo_expected, "LPO approval DMG0041 " + lpo_number,
                    lambda: approve_lpo(page, lpo_number, "DMG0041")
                )

                # 8-10. Log out, log in, approve exact same LPO.
                for next_user in ("DMG0013", "DMG0051", "DMG0052"):
                    logout(page, current_user)
                    current_user = next_user
                    login(page, current_user)
                    report["lpo_approvals"][current_user] = monitor_print_action(
                        print_monitor, "LPO", lpo_expected,
                        "LPO approval " + current_user + " " + lpo_number,
                        lambda: approve_lpo(page, lpo_number, current_user)
                    )

                # 11. After DMG0052 final LPO approval, switch to DMG0041.
                logout(page, current_user)
                current_user = "DMG0041"
                login(page, current_user)

                # 12. Search Goods Receipt Note, CREATE and SAVE exact LPO GRN.
                grn_pdf_checkpoint = print_monitor.checkpoint()
                grn_number = save_grn_from_lpo(page, pi, report["lpo"])
                report["grn_number"] = grn_number
                grn_expected = {"transaction": grn_number, "po_reference": lpo_number,
                                "vendor": report["lpo"]["vendor"], "item": pi["item"],
                                "received_qty": report["lpo"]["quantity"],
                                "invoice_no": getattr(page, "_grn_invoice_no", None),
                                "invoice_date": getattr(page, "_grn_invoice_date", None),
                                "description": getattr(page, "_grn_description", None)}
                grn_expected["_print_creation"] = getattr(page, "_strict_grn_print_creation", None)
                emit('erp_values', process='Goods Receipt Note', transaction=grn_number,
                     values={key: grn_expected.get(key) for key in ('transaction', 'po_reference', 'vendor', 'item', 'received_qty', 'invoice_no', 'invoice_date', 'description')},
                     note='Values captured during GRN creation; submission and final ERP persistence need status confirmation')
                print_monitor.validate_new(grn_pdf_checkpoint, "GRN",
                    grn_expected, "GRN created " + grn_number)

                # 13. Select the newly saved GRN transaction and SUBMIT.
                report["grn_submit"] = monitor_print_action(
                    print_monitor, "GRN", grn_expected,
                    "GRN submitted " + grn_number,
                    lambda: submit_saved_grn(page, grn_number)
                )

                # Prepare for the next PI record if TOTAL_RECORDS > 1.
                if record is not TEST_DATA[TOTAL_RECORDS - 1]:
                    logout(page, current_user)
                    current_user = "DMG0013"
                    login(page, current_user)

        except Exception as error:
            log("AUTOMATION ERROR")
            print("Current URL:", page.url)
            traceback.print_exc()
            capture_failure(page, "AUTOMATION")
            screenshot_failure(page, "AUTOMATION", [str(error)])
            emit('blocked', name='Remaining dependent procurement stages',
                 status='BLOCKED', actual='An earlier stage failed; no downstream retries were attempted.')
            raise
        finally:
            if trace_started:
                try:
                    context.tracing.stop(path=str(run_directory() / 'trace.zip'))
                except Exception as exc:
                    emit('trace_warning', message=str(exc)[:500])
            print_monitor.save_report()
            log("FINAL EXECUTION REPORT")
            for result in results:
                print(json.dumps(result, indent=2, default=str))
            if owns_browser:
                if not run_directory():
                    try:
                        input("\nPress ENTER to close browser...")
                    except EOFError:
                        pass
                browser.close()
            # A reused managed browser remains open. Only this CDP client detaches.
            if stop_button_process is not None and stop_button_process.poll() is None:
                stop_button_process.terminate()

    if print_monitor.has_failures:
        raise AssertionError("Print validation failed. See print_validation_report.html; saved ERP transactions are not undone.")


if __name__ == "__main__":
    main()

