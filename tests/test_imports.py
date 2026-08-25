def test_core_packages_import():
    import flood_engine
    import sensors
    import routing
    import replay
    import backend

    assert flood_engine is not None
    assert sensors is not None
    assert routing is not None
    assert replay is not None
    assert backend is not None
