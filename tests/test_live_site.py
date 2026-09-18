# -*- coding: utf-8 -*-
import urllib.request
from pathlib import Path

def test_live():
    urls = [
        'http://localhost:8080/index.html',
        'http://localhost:8080/style.css',
        'http://localhost:8080/app.js',
        'http://localhost:8080/assets/images/model-portrait.jpg',
        'http://localhost:8080/assets/images/model-look-01.jpg',
        'http://localhost:8080/assets/images/model-look-02.jpg',
        'http://localhost:8080/assets/images/model-look-03.jpg',
    ]
    for u in urls:
        resp = urllib.request.urlopen(u)
        assert resp.status == 200, f'HTTP failed for {u}'
    print('PASS: All 7 HTTP endpoints return 200 OK')

    html = Path('index.html').read_text(encoding='utf-8')
    assert 'id="hero-section"' in html
    assert 'id="lookbook-section"' in html
    assert 'id="pieces-section"' in html
    assert 'id="craft-section"' in html
    assert 'id="cart-drawer"' in html
    assert 'data-pose-index="0"' in html
    assert 'data-pose-index="3"' in html
    assert 'data-garment-id="g-01"' in html
    assert 'data-garment-id="g-05"' in html
    assert 'id="consult-order-form"' in html
    print('PASS: HTML contains all expected sections and anchors')

    css = Path('style.css').read_text(encoding='utf-8')
    assert '--bg-canvas: #F8F6F0;' in css
    assert '--color-accent: #8E5230;' in css
    assert '@media (max-width: 768px)' in css
    assert '.cart-drawer' in css
    print('PASS: CSS contains all design tokens and responsive media queries')

    js = Path('app.js').read_text(encoding='utf-8')
    assert 'pootone_wishlist_items' in js
    assert 'addToWishlist' in js
    assert 'updateQty' in js
    assert 'removeItem' in js
    assert 'localStorage' in js
    print('PASS: app.js contains all state operations and storage handlers')

    print('=== ALL LIVE SITE CHECKS PASSED ===')

if __name__ == '__main__':
    test_live()
