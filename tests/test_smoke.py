import token_oracle

def test_version_present():
    assert isinstance(token_oracle.__version__, str)
    assert token_oracle.__version__
