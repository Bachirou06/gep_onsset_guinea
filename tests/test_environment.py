def test_onsset_imports(gep_path):
    import onsset
    assert hasattr(onsset, "SettlementProcessor")


def test_sample_fixture_shape(sample_calibrated):
    import pandas as pd
    df = pd.read_csv(sample_calibrated)
    assert len(df) == 500 and "hc_count_com_hc" in df.columns
