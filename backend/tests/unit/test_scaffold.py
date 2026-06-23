def test_backend_scaffold_imports() -> None:
    import src

    assert src.__doc__ is not None
