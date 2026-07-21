def test_policy_totals_and_hard_caps(config):
    assert len(config.instruments) == 15
    assert sum(m.target_weight for m in config.modules.values()) == 1
    assert sum(config.modules[k].target_weight for k in ("dividend", "broad_market", "technology")) == 0.42
    assert config.technology_weight_cap == 0.15
    assert [s.cumulative_amount_cny for s in config.technology_stages] == [25_000, 70_000, 115_000, 150_000]
    assert config.initial_authorization["risk_assets"] == {"minimum_cny": 105_000, "maximum_cny": 125_000}
    assert config.initial_authorization["technology"]["maximum_cny"] == 25_000
