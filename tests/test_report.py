from pathlib import Path

from bckg.extract import extract
from bckg.questions import View
from bckg.report import render

FIXTURES = Path(__file__).parent / 'fixtures'


def test_report_answers_every_question_without_parameters():
    page = render(View(extract(FIXTURES / 'products.yaml')[0]), title='Fixture <graph>', graph_url='graph.json')
    assert page.startswith('<!doctype html>')
    assert '<title>Fixture &lt;graph&gt;</title>' in page  # titles are escaped
    assert 'id="q-id-collisions"' in page and '1 found' in page  # Alpha and Beta share table extension 50000
    assert 'id="q-contract-coverage"' in page
    assert 'id="q-feature-trace"' not in page  # needs a parameter, listed under "Questions with a parameter"
    assert 'feature_trace' in page
    assert 'href="graph.json"' in page
    assert '<script' not in page and 'http://' not in page  # self-contained


def test_report_intro_legend_and_product_cards():
    view = View(extract(FIXTURES / 'products.yaml')[0])
    default = render(view)
    assert 'class="lead"' in default and 'How to read this page' in default
    assert 'id="products"' in default and '<article class="product"><h3>Alpha</h3>' in default
    assert 'app 50000-50099' in default and 'tests 60000-60099' in default  # the test app is folded into Alpha
    assert 'Tests in <i>Alpha Tests</i> (1 codeunit)' in default
    assert '<h3>Alpha Tests</h3>' not in default and '<b>Alpha Tests</b>' not in default
    assert '1 of 1 tested' in default
    custom = render(view, intro='<p class="lead">Custom intro</p>')
    assert 'Custom intro' in custom and 'built from the AL source of the apps below' not in custom


def test_report_overlap_matrix_and_outro():
    view = View(extract(FIXTURES / 'products.yaml')[0])
    page = render(view, outro='<h2>Next</h2><a class="button" href="https://example.com">Go</a>')
    assert 'class="matrix"' in page and 'Alpha and Beta: 1 standard objects' in page
    assert '<section id="next" class="outro"><h2>Next</h2>' in page
    assert 'id="next"' not in render(view)


def test_report_extra_product_cards():
    view = View(extract(FIXTURES / 'products.yaml')[0])
    page = render(view, extra_products='<article class="product private"><h3>Hidden</h3></article>')
    products = page[page.index('id="products"'):page.index('</section>', page.index('id="products"'))]
    assert products.index('<h3>Beta</h3>') < products.index('<h3>Hidden</h3>')  # after the generated cards
