def test_core_packages_import():
    import backend
    import flood_engine
    import replay
    import routing
    import sensors

    assert flood_engine is not None
    assert sensors is not None
    assert routing is not None
    assert replay is not None
    assert backend is not None
