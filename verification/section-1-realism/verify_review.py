"""Check the offline review page in real Edge at desktop and phone sizes."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PAGE = ROOT/'deliverables/section-1-realism/index.html'
checks = []
with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1100}, device_scale_factor=1)
    failures = []
    page.on('pageerror', lambda error: failures.append(str(error)))
    page.goto(PAGE.as_uri(), wait_until='load')
    page.locator('#hero').evaluate('(image) => image.decode()')
    assert page.locator('#hero').evaluate('(image) => image.naturalWidth') == 3200
    page.screenshot(path=str(HERE/'review-desktop.png'))
    page.get_by_role('button', name='Вечер', exact=True).click()
    page.locator('#hero').evaluate('(image) => image.decode()')
    assert page.locator('#hero').get_attribute('src') == 'images/02-overview-evening.png'
    assert page.locator('#hero-link').get_attribute('href') == 'images/02-overview-evening.png'
    assert page.get_by_role('button', name='Вечер', exact=True).get_attribute('aria-pressed') == 'true'
    page.get_by_role('button', name='День', exact=True).click()
    page.locator('#hero').evaluate('(image) => image.decode()')
    assert page.locator('#hero').get_attribute('src') == 'images/01-overview-day.png'
    checks.append('desktop day/evening toggle changes original image and link')
    page.set_viewport_size({'width': 390, 'height': 900})
    page.screenshot(path=str(HERE/'review-mobile.png'))
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    checks.append('mobile page has no horizontal overflow')
    page.locator('#detail').scroll_into_view_if_needed()
    page.locator('#detail img').evaluate('(image) => image.decode()')
    assert page.locator('#detail img').evaluate('(image) => image.naturalWidth') == 3200
    page.locator('#references').scroll_into_view_if_needed()
    for image in page.locator('.refs img').all():
        image.evaluate('(image) => image.decode()')
        assert image.evaluate('(image) => image.naturalWidth') > 0
    checks.append('detail image and both references load offline')
    page.locator('#previous').scroll_into_view_if_needed()
    page.locator('#previous img').evaluate('(image) => image.decode()')
    page.set_viewport_size({'width': 1440, 'height': 1100})
    page.evaluate('window.scrollTo(0, 0)')
    page.screenshot(path=str(HERE/'review-desktop-full.png'), full_page=True)
    assert not failures, failures
    checks.append('no JavaScript errors')
    browser.close()
(HERE/'ui-review.json').write_text(json.dumps({'passed': True, 'checks': checks,
    'browser': 'Microsoft Edge', 'viewports': [[1440, 1100], [390, 900]]}, indent=2), encoding='utf-8')
print('OFFLINE_REVIEW_UI_PASSED', len(checks))
