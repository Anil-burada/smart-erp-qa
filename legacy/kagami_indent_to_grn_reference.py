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
# Run: python ERP_FULL_AUTOMATION_GRN_OK_SAVE_SUBMIT_FIXED.py
# Browser interactions are NOT verified against your ERP login.
# Test in an authorized non-production environment first.
# ============================================================

# FULL SINGLE-FILE ERP AUTOMATION (PI -> LPO -> GRN)
# Based on your attached script and captured GRN locator JSON.
# Playwright interactions are not live-verified; use a test ERP.



import json
import os
import signal
import subprocess
import sys

import random

import re
from difflib import SequenceMatcher

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

SCREENSHOTS = BASE / "screenshots"



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
    """Log in with credentials supplied via the local environment."""
    allowed_users = {"DMG0041", "DMG0013", "DMG0051", "DMG0052"}
    if username not in allowed_users:
        raise ValueError(f"Unexpected ERP account: {username}")

    log(f"ERP LOGIN - {username}")
    username_input = page.locator("#username")
    password_input = page.locator("#password")
    expect(username_input).to_be_visible(timeout=TIMEOUT)
    username_input.fill(username)
    password = os.environ.get(f"ERPQA_KAGAMI_{username}_PASSWORD", "")
    if not password:
        raise RuntimeError(f"Missing local password environment variable for {username}")
    password_input.fill(password)
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



    target = decimal(quantity)



    if target <= 0:



        raise ValueError(

            "Indent Quantity must be greater than zero"

        )



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



                    return



            except Exception:

                pass



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



def validate_then_save(

    page,

    tax_label

):



    stage = "ITEM"



    try:



        if norm(tax_label) != "pgst":



            raise RuntimeError(

                "Selected Tax Definition is not PGST"

            )



        expected, errors = validate_item(page)



        if errors:



            # Optional screenshot on failure:
            # screenshot_failure(page, stage, errors)



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



            # Optional screenshot on failure:
            # screenshot_failure(page, stage, errors)



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



        save.click()



        print(

            "LPO Save button clicked; "

            "ERP persistence not yet "

            "independently verified"

        )



        return True



    except Exception as error:



        # Optional screenshot on failure:
        # screenshot_failure(page, stage, [str(error)])



        return False





# ============================================================

# CREATE LOCAL PURCHASE ORDER

# ============================================================



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

    saved = validate_then_save(

        page,

        tax

    )



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

PRINT_REPORTS = BASE / "reports" / "print_validation"
PRINT_REQUIRE_PDF = False  # Set True ONLY if every monitored action must print.
PRINT_CAPTURE_WAIT_MS = 1600
PRINT_PREVIEW_ENABLED = True
PRINT_PREVIEW_DURATION_MS = 5000  # Wait five seconds before continuing.

PRINT_CAPTURE_MAX_BYTES = 15 * 1024 * 1024

# Only fields known to appear on the print should be listed here.
# Regexes deliberately capture a labeled value rather than searching any number.
# These are fields actually shown in typical PI/LPO/GRN layouts.
# A field is validated ONLY if its label can be found in the PDF. If a
# particular project uses different labels, update this mapping.
PRINT_FIELD_RULES = {
    "PI": {
        "transaction": ["Indent No", "Indent No.", "Indent Number"],
        "date": ["Indent Date", "Required Date"],
        "department": ["Department"],
        "purchase": ["Purchase Type"],
        "kind": ["Indent Type"],
        "section": ["Section"],
        "asset": ["Equipment", "Asset"],
        # PI item_code, item_name, UOM, quantity are validated by
        # the TABLE validator below, not as normal labels.
    },
    "LPO": {
        "transaction": ["PO No", "LPO No", "Transaction No"],
        "department": ["Department"],
        "vendor": ["Vendor", "Supplier"],
        "item": ["Item Name", "Item Code"],
        "quantity": ["Qty", "Quantity"],
        "unit_price": ["Unit Price", "Rate", "Price"],
        "discount_percentage": ["Discount %", "Discount Percent"],
        "gross": ["Gross Amount", "Total Gross Amount"],
        "discount_amount": ["Discount Amount", "Total Discount Amount"],
        "tax_amount": ["Tax Amount", "Total Taxes Amount"],
        "net": ["Net Amount", "Total Net Amount"],
    },
    "GRN": {
        "transaction": ["GRN No", "Transaction No", "Goods Receipt Note No"],
        "po_reference": ["Local PO", "PO Reference"],
        "vendor": ["Vendor"],
        "invoice_no": ["Invoice No", "Invoice Number"],
        "invoice_date": ["Invoice Date"],
        "description": ["Description"],
        "item": ["Item Name", "Item Code"],
        "received_qty": ["Received Qty", "Qty / Accepted Qty"],
    },
}


def print_safe_name(value):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value))[:100]


def print_normalized(value):
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def print_is_pdf(data):
    return bool(data and data.lstrip()[:5] == b"%PDF-")


class ERPPrintMonitor:
    """Observe printable PDF files without clicking unconfirmed ERP controls."""

    def __init__(self, context, page):
        self.context = context
        self.page = page
        self.documents = []
        self.results = []
        self.counter = 0
        self.last_viewers = []
        PRINT_REPORTS.mkdir(parents=True, exist_ok=True)
        context.on("response", self._on_response)
        page.on("download", self._on_download)
        # ERP may display a PDF in an iframe using a browser blob: URL.
        # Such documents do not trigger a new PDF response or download.

    def _capture_embedded_pdf(self):
        """Locate embedded print viewer and attempt byte capture.

        The Chrome PDF viewer's <canvas> is only a thumbnail; the enclosing
        iframe/embed/object URL is the useful runtime locator. Cross-origin
        Chrome extension internals are intentionally not inspected.
        """
        import base64
        script = r"""async () => {
            const elements = [...document.querySelectorAll(
              'iframe, embed, object, a[href$=".pdf"]'
            )];
            const viewers = elements.map(el => {
              const url = el.getAttribute('src') || el.getAttribute('data') ||
                          el.getAttribute('href') || '';
              const rect = el.getBoundingClientRect();
              return {tag:el.tagName.toLowerCase(), id:el.id || '',
                title:el.getAttribute('title') || '', type:el.getAttribute('type') || '',
                url, visible: rect.width > 10 && rect.height > 10,
                width:Math.round(rect.width),height:Math.round(rect.height)};
            }).filter(item => item.visible || /pdf|blob:|chrome-extension:/i.test(item.url));
            const results=[];
            for (const view of viewers) {
                const src=view.url;
                if (!src || /^(chrome-extension:|about:)/i.test(src)) continue;
                // Do not fetch unrelated pages: network listener already handles
                // ordinary PDF responses. Fetch only PDF-ish embeds/URLs.
                if (!/\.pdf(?:[?#]|$)|^blob:|^data:application\/pdf|\/pdf\b/i.test(src)
                    && view.type !== 'application/pdf') continue;
                try {
                    const response=await fetch(src,{credentials:'include'});
                    if (!response.ok) throw Error('HTTP '+response.status);
                    const bytes=await response.blob();
                    if (bytes.size > 15000000) throw Error('PDF too large');
                    const b64=await new Promise((resolve,reject)=>{
                        const reader=new FileReader();
                        reader.onload=()=>resolve(String(reader.result).split(',')[1]);
                        reader.onerror=reject;
                        reader.readAsDataURL(bytes);
                    });
                    results.push({url:src,data:b64});
                } catch(e){results.push({url:src,error:String(e)});}
            }
            return {viewers,results};
        }"""
        detected = []
        for active_page in self.context.pages:
            try:
                output = active_page.evaluate(script)
                for viewer in output.get('viewers', []):
                    detected.append(viewer)
                    print('PRINT VIEWER LOCATOR:', viewer['tag'],
                          'id=' + repr(viewer['id']), 'src=' + repr(viewer['url'][:180]))
                for entry in output.get('results', []):
                    if entry.get('data'):
                        self._store(base64.b64decode(entry['data']),
                                    'embedded:' + entry['url'][:120])
                    else:
                        print('PRINT VIEWER FETCH BLOCKED:', entry.get('error'))
            except Exception as error:
                print('PRINT VIEWER INSPECTION FAILED:', str(error)[:180])
        self.last_viewers = detected
        return detected

    def _store(self, content, origin):
        if not print_is_pdf(content) or len(content) > PRINT_CAPTURE_MAX_BYTES:
            return
        # Avoid duplicate network/download captures of the same document.
        import hashlib
        digest = hashlib.sha256(content).hexdigest()
        if any(x["sha256"] == digest for x in self.documents):
            return
        self.counter += 1
        path = PRINT_REPORTS / f"captured_{self.counter:03d}.pdf"
        path.write_bytes(content)
        entry = {"path": str(path), "origin": origin, "sha256": digest}
        self.documents.append(entry)
        print("PRINT PDF CAPTURED:", path)

    def _on_response(self, response):
        try:
            headers = response.headers
            content_type = headers.get("content-type", "").lower()
            disposition = headers.get("content-disposition", "").lower()
            url = response.url.lower().split("?")[0]
            if ("application/pdf" not in content_type
                    and "application/octet-stream" not in content_type
                    and "pdf" not in disposition and not url.endswith(".pdf")):
                return
            data = response.body()
            self._store(data, response.url)
        except Exception as error:
            print("PDF response could not be captured:", str(error)[:200])

    def _on_download(self, download):
        try:
            if not download.suggested_filename.lower().endswith(".pdf"):
                return
            data = Path(download.path()).read_bytes()
            self._store(data, "download:" + download.suggested_filename)
        except Exception as error:
            print("PDF download capture issue:", str(error)[:200])

    def checkpoint(self):
        """Call immediately BEFORE an action that may automatically open Print."""
        return len(self.documents)

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

    def validate_new(self, start, doc_type, expected, label):
        """Validate PDFs captured since checkpoint; no PDF means NOT_CAPTURED."""
        self.page.wait_for_timeout(PRINT_CAPTURE_WAIT_MS)
        self._capture_embedded_pdf()
        new_docs = self.documents[start:]
        if not new_docs:
            result = {"action": label, "document_type": doc_type,
                      "status": "FAIL_NO_PDF" if PRINT_REQUIRE_PDF else "NOT_CAPTURED",
                      "message": "Print viewer detection alone does not expose PDF text. Check PRINT VIEWER LOCATOR logs and actual PDF response.",
                      "detected_viewers": self.last_viewers}
            self.results.append(result)
            print("PRINT CHECK:", result["status"], "-", label)
            if PRINT_REQUIRE_PDF:
                raise AssertionError(f"Expected PDF not captured after {label}")
            return result
        found = []
        for entry in new_docs:
            result = validate_erp_print_pdf(entry["path"], doc_type, expected, label)
            self.results.append(result)
            print_show_failure_on_current_page(self.page, label, result)
            self.show_annotated_preview(result, label)
            found.append(result)
        if any(x["status"] == "FAIL" for x in found):
            print("PRINT VALIDATION FAIL:", label, "- same-page evidence captured")
            # Do not stop ERP workflow automatically; report evidence for investigation.
        return found[-1]

    def save_report(self):
        path = PRINT_REPORTS / "print_validation_report.json"
        path.write_text(json.dumps(self.results, indent=2, default=str), encoding="utf-8")
        print("PRINT VALIDATION REPORT:", path)



def validate_pi_item_table(pdf, expected, equivalent):
    """Validate an actual PI item row via PDF column geometry.

    No hardcoded page coordinates. Only check fields supported by form data.
    Missing/ambiguous columns are UNMAPPED, not false red failures.
    """
    import pymupdf as fitz

    def result(key, wanted, actual=None, status='UNMAPPED', page_no=None):
        r = {'field': key, 'expected': str(wanted), 'actual': actual,
             'status': status}
        if page_no is not None:
            r['page'] = page_no + 1
        print(f'PRINT PI ITEM {status} | {key} | expected={wanted} printed={actual}')
        return r

    item_full = str(expected.get('item') or '').strip()
    quantity = expected.get('qty')
    uom = expected.get('uom')
    if not item_full and quantity is None and not uom:
        return []
    match = re.match(r'^([A-Za-z0-9]+)\s+-\s+(.+)$', item_full)
    item_code, item_name = ((match.group(1), match.group(2)) if match
                             else (None, item_full))
    checks = [('item_code', item_code), ('item_name', item_name),
              ('uom', uom), ('qty', quantity)]
    checks = [(k, v) for k, v in checks if v is not None and str(v).strip()]

    for page_no, page in enumerate(pdf):
        words = page.get_text('words', sort=True)
        if not words:
            continue
        # PDF text sometimes splits "Item Code" across words. Find the header
        # by its tokens near a "Qty" header on the same row.
        qty_headers = [w for w in words if w[4].strip().casefold() == 'qty']
        for qw in qty_headers:
            yh = (qw[1] + qw[3]) / 2
            header_words = [w for w in words if abs((w[1]+w[3])/2-yh) < 14]
            # Find Item/Code/UoM/Qty centers from actual printed header words.
            def center_of(token, prefer_before=None):
                hits = [w for w in header_words if w[4].strip(' :').casefold() == token]
                if prefer_before is not None:
                    hits = [w for w in hits if (w[0]+w[2])/2 < prefer_before]
                if not hits:
                    return None
                w = hits[0]
                return (w[0]+w[2])/2
            qty_x = (qw[0]+qw[2])/2
            uom_x = center_of('uom', qty_x)
            code_x = center_of('code', qty_x)
            name_x = center_of('name', qty_x)
            if not all(x is not None for x in (qty_x, uom_x, code_x, name_x)):
                continue
            centers = sorted([('item_code',code_x),('item_name',name_x),
                              ('uom',uom_x),('qty',qty_x)],key=lambda x:x[1])
            # Headers not listed as checkable fields still determine cell edges.
            # Include previous price header if present, to prevent UOM reading price.
            prev_x = center_of('previous',qty_x)
            if prev_x is not None:
                centers.append(('previous_price',prev_x))
                centers.sort(key=lambda x:x[1])
            bounds = {}
            for j,(k,x) in enumerate(centers):
                left=(centers[j-1][1]+x)/2 if j else max(page.rect.x0,x-65)
                right=(x+centers[j+1][1])/2 if j+1<len(centers) else min(page.rect.x1,x+65)
                bounds[k]=(left,right)
            header_bottom = max(w[3] for w in header_words)
            # One data row directly beneath the header. Values may wrap to 2 lines.
            row_words=[w for w in words if w[1] >= header_bottom+1 and w[1] <= header_bottom+55]
            if not row_words:
                continue
            # Require a printed row with item code OR expected item name token.
            row_line = ' '.join(w[4] for w in row_words).casefold()
            # Do not require an exact item-code hit to find the row: an
            # imperfectly printed code must still be evaluated, not UNMAPPED.
            # This validator covers the first PI item row; multi-item prints
            # require row identification using additional field evidence.
            results=[]
            for key,wanted in checks:
                left,right=bounds[key]
                cell_words=[w for w in row_words if left <= (w[0]+w[2])/2 < right]
                cell_words.sort(key=lambda w:(round(w[1]/5),w[0]))
                if not cell_words:
                    results.append(result(key,wanted))
                    continue
                actual=' '.join(w[4] for w in cell_words).strip()
                extra = {}
                if key == 'item_code':
                    # Ignore the S.No column and avoid treating its digit as
                    # part of the item code. Compare the printed code token.
                    actual_codes = re.findall(r'[A-Za-z0-9]{5,}', actual)
                    if len(actual_codes) == 1:
                        actual = actual_codes[0]
                    elif len(actual_codes) > 1:
                        # Split text or multiple codes are ambiguous: do not
                        # claim a successful item-code comparison.
                        results.append(result(key, wanted, actual))
                        continue
                    else:
                        results.append(result(key, wanted, actual))
                        continue
                    expected_code = re.sub(r'[^a-z0-9]', '', str(wanted).casefold())
                    printed_code = re.sub(r'[^a-z0-9]', '', actual.casefold())
                    similarity = 100.0 * SequenceMatcher(
                        None, expected_code, printed_code
                    ).ratio()
                    extra['similarity_percent'] = round(similarity, 2)
                    # Requested classification. Similarity PASS does not
                    # guarantee the ERP item master code is identical.
                    if similarity >= 70:
                        status, color = 'PASS', (0.04, 0.65, 0.20)
                    elif similarity >= 50:
                        status, color = 'PARTIAL_MATCH', (1, 0.65, 0)
                    else:
                        status, color = 'FAIL', (1, 0.06, 0.06)
                else:
                    if key == 'item_name':
                        passed = re.sub(r'[^a-z0-9]', '', actual.casefold()) == re.sub(r'[^a-z0-9]', '', str(wanted).casefold())
                    else:
                        passed = equivalent(key, actual, wanted)
                    status = 'PASS' if passed else 'FAIL'
                    color = (0.04, 0.65, 0.2) if passed else (1, 0.06, 0.06)
                rect=fitz.Rect(cell_words[0][:4])
                for w in cell_words[1:]: rect |= fitz.Rect(w[:4])
                rect.x0-=2; rect.x1+=2; rect.y0-=2; rect.y1+=2
                page.draw_rect(rect,color=color,width=2.4,overlay=True)
                entry = result(key, wanted, actual, status, page_no)
                entry.update(extra)
                results.append(entry)
            return results
    return [result(k,v) for k,v in checks]

def validate_erp_print_pdf(pdf_path, document_type, expected, label):
    """Compare creation-time values to the correct labeled PDF field.

    Color the printed value GREEN on match and RED on mismatch. A field whose
    label/position cannot be isolated is UNMAPPED, never silently PASS.
    """
    try:
        import pymupdf as fitz
    except ImportError:
        return {"action": label, "status": "NOT_CONFIGURED",
                "message": "pip install pymupdf"}

    def clean(value):
        return re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip().casefold()

    def tokens(value):
        return re.findall(r"[a-z0-9]+", clean(value))

    def equivalent(key, actual, wanted):
        actual, wanted = clean(actual), clean(wanted)
        if key in {"qty", "quantity", "received_qty", "unit_price", "gross",
                   "discount_amount", "tax_amount", "net", "discount_percentage"}:
            try:
                return Decimal(re.sub(r"[^0-9.\-]", "", actual)) == Decimal(
                    re.sub(r"[^0-9.\-]", "", wanted))
            except Exception:
                return False
        if key in {"vendor", "item"}:
            # Vendors and items can show a numeric master code on either side.
            actual = re.sub(r"^\d+\s*-\s*|\s*-\s*\d+$", "", actual)
            wanted = re.sub(r"^\d+\s*-\s*|\s*-\s*\d+$", "", wanted)
        if key == "date" or key == "invoice_date":
            return actual.replace("-", "/") == wanted.replace("-", "/")
        return tokens(actual) == tokens(wanted)

    def union(words):
        result = fitz.Rect(words[0][:4])
        for w in words[1:]:
            result |= fitz.Rect(w[:4])
        return result

    def find_label(words, aliases):
        # Word sequence matching is more reliable than PDF extract_text lines,
        # especially for two-column purchase forms.
        candidates = []
        for alias in aliases:
            parts = tokens(alias)
            for i in range(len(words)-len(parts)+1):
                group = words[i:i+len(parts)]
                if [tokens(w[4])[0] if tokens(w[4]) else '' for w in group] != parts:
                    continue
                r = union(group)
                # Keep label words spatially together on the same printed line.
                if max(w[3] for w in group) - min(w[1] for w in group)  > 22:
                    continue
                candidates.append((r, alias))
            if candidates:
                break
        return candidates

    def word_value_near_label(page, anchor, aliases, key):
        words = page.get_text("words", sort=True)
        # For item table columns, the value is below the header; for form
        # fields, the value is usually to the right or on the next line.
        nearby = [w for w in words if (w[0] >= anchor.x1 - 2 and
                  abs((w[1]+w[3])/2 - (anchor.y0+anchor.y1)/2) < 8 and
                  w[0] - anchor.x1 < 230)]
        if nearby:
            nearby.sort(key=lambda w:w[0])
            # Do not absorb the next labeled column past a large gap.
            sample = [nearby[0]]
            for w in nearby[1:]:
                if w[0]-sample[-1][2] > 24: break
                sample.append(w)
            return ' '.join(w[4] for w in sample).strip(' :'), union(sample)
        beneath = [w for w in words if w[1] >= anchor.y1 - 1 and
                   0 <= w[1]-anchor.y1 <= 27 and
                   (anchor.x0-4 <= (w[0]+w[2])/2 <= anchor.x1+35)]
        if beneath:
            nearest_y = min(w[1] for w in beneath)
            sample = [w for w in beneath if abs(w[1]-nearest_y) < 5]
            return ' '.join(w[4] for w in sample).strip(' :'), union(sample)
        return None, None

    rules = PRINT_FIELD_RULES.get(document_type, {})
    checks = [(key, str(expected[key]).strip(), aliases)
              for key, aliases in rules.items()
              if expected.get(key) is not None and str(expected[key]).strip()]
    if not checks:
        return {"action": label, "status": "NOT_CONFIGURED", "document_type": document_type}

    results=[]
    with fitz.open(pdf_path) as pdf:
        if not any(p.get_text("text").strip() for p in pdf):
            return {"action": label, "status": "NOT_READABLE", "pdf":str(pdf_path)}
        for key, wanted, aliases in checks:
            candidates=[]
            for page_no, page in enumerate(pdf):
                words=page.get_text('words', sort=True)
                for rect, alias in find_label(words, aliases):
                    actual, value_rect = word_value_near_label(page,rect,aliases,key)
                    if actual and value_rect:
                        candidates.append((page_no,actual,value_rect))
            # Require unique label/value association; guessing can give false PASS.
            if len(candidates) != 1:
                result={"field":key,"expected":wanted,"actual":None,
                        "status":"UNMAPPED","candidates":len(candidates)}
                print(f"PRINT FIELD UNMAPPED | {label} | {key} | labels={len(candidates)}")
            else:
                page_no,actual,rect=candidates[0]
                passed=equivalent(key,actual,wanted)
                color=(0.04,0.65,0.20) if passed else (1,0.06,0.06)
                expanded=fitz.Rect(rect)
                expanded.x0-=2; expanded.y0-=2; expanded.x1+=2; expanded.y1+=2
                pdf[page_no].draw_rect(expanded,color=color,width=2.4,overlay=True)
                result={"field":key,"expected":wanted,"actual":actual,
                        "status":"PASS" if passed else "FAIL","page":page_no+1}
                print(f"PRINT FIELD {'PASS GREEN' if passed else 'FAIL RED'} | {label} | {key} | Expected={wanted} Actual={actual}")
            results.append(result)
        if document_type == 'PI':
            results.extend(validate_pi_item_table(pdf, expected, equivalent))
        status=('FAIL' if any(r['status']=='FAIL' for r in results) else
                'UNMAPPED' if any(r['status']=='UNMAPPED' for r in results) else 'PASS')
        stem=print_safe_name(label)
        output=PRINT_REPORTS / f"{stem}_DYNAMIC_GREEN_RED.pdf"
        pdf.save(str(output),garbage=3,deflate=True)
        screenshots=[]
        # Screenshot only on FAIL (user preference); annotated PDF always saved.
        if status=='FAIL':
            for i,page in enumerate(pdf):
                path=PRINT_REPORTS/f"{stem}_page_{i+1}_FAIL.png"
                page.get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False).save(str(path))
                screenshots.append(str(path))
    return {"action":label,"document_type":document_type,"pdf":str(pdf_path),
            "annotated_pdf":str(output),"status":status,"fields":results,
            "mismatches":[r for r in results if r['status']=='FAIL'],
            "unmapped":[r for r in results if r['status']=='UNMAPPED'],
            "screenshots":screenshots}


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
            box.textContent=messages.join('\n');document.body.appendChild(box);
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
        raise RuntimeError(
            f'Warehouse quantity changed: expected {received_qty}, got {actual}'
        )
    print('PASS - Warehouse quantity:', actual)

    # Two different OK buttons, one for each nested editor.
    grn_modal_ok(page, 'Edit Warehouse Details')
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
    grn_exact_visible_button(page, 'SAVE').click()
    return find_new_grn(page, before)


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
    if os.environ.get('ERPQA_RUN_LEGACY_WRITES') != 'YES_IN_AUTHORIZED_TEST':
        raise RuntimeError('Legacy end-to-end write script is disabled by default. Use the reviewed approval-plan dashboard instead. Set ERPQA_RUN_LEGACY_WRITES=YES_IN_AUTHORIZED_TEST only in an authorized nonproduction environment.')
    if not 1 <= TOTAL_RECORDS <= len(TEST_DATA):
        raise ValueError("TOTAL_RECORDS is outside TEST_DATA")

    results = []
    stop_button_process = start_emergency_stop_button()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, slow_mo=500, args=["--start-maximized"]
        )
        context = browser.new_context(no_viewport=True)
        page = context.new_page()
        page.set_default_timeout(TIMEOUT)
        print_monitor = ERPPrintMonitor(context, page)

        try:
            page.goto(ERP_URL, wait_until="domcontentloaded", timeout=60000)
            current_user = "DMG0013"
            login(page, current_user)

            for record in TEST_DATA[:TOTAL_RECORDS]:
                # 1. DMG0013 creates and SUBMITS Purchase Indent.
                pi_pdf_checkpoint = print_monitor.checkpoint()
                pi = create_indent(page, record)
                print_monitor.validate_new(
                    pi_pdf_checkpoint, "PI",
                    pi,
                    "PI created and submitted " + pi["transaction"]
                )
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
                                    tax_amount=tax_amount, net=money(gross-discount_amount+tax_amount))
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
            # Screenshot-taking code kept disabled by default.
            # screenshot_failure(page, "AUTOMATION", [str(error)])
        finally:
            print_monitor.save_report()
            log("FINAL EXECUTION REPORT")
            for result in results:
                print(json.dumps(result, indent=2, default=str))
            try:
                input("\nPress ENTER to close browser...")
            except EOFError:
                pass
            browser.close()
            if stop_button_process is not None and stop_button_process.poll() is None:
                stop_button_process.terminate()


if __name__ == "__main__":
    main()

