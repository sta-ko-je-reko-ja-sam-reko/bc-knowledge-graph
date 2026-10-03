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
    assert '1 feature<' in default  # singular
    custom = render(view, intro='<p class="lead">Custom intro</p>')
    assert 'Custom intro' in custom and 'built from the AL source of the apps below' not in custom
