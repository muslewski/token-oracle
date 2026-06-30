import oracle

def test_version_present():
    assert isinstance(oracle.__version__, str)
    assert oracle.__version__
