from veltix._vendor.avyra import __version__


def test_version_exists():
    assert isinstance(__version__, str)
    assert len(__version__) > 0
