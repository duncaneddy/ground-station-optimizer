
import pytest

from gsopt.scenarios import ScenarioGenerator

def test_add_random_satellites():
    scengen = ScenarioGenerator()

    assert scengen.num_satellites == 0

    scengen.add_random_satellites(10, alt_range=(300, 1000))
    assert scengen.num_satellites == 10

def test_add_random_satellites_with_seed():
    scengen = ScenarioGenerator(seed=42)
    assert scengen.get_seed() == 42

    assert scengen.num_satellites == 0

    scengen.add_random_satellites(5, alt_range=(300, 1000))

    # Confirm that the same seed produces the same result
    assert scengen.satellites[0].satcat_id == '41898'
    assert scengen.satellites[1].satcat_id == '47845'
    assert scengen.satellites[2].satcat_id == '53277'
    assert scengen.satellites[3].satcat_id == '53782'
    assert scengen.satellites[4].satcat_id == '55058'

def test_add_satellite_by_id():
    scengen = ScenarioGenerator()

    assert scengen.num_satellites == 0

    scengen.add_satellite('25544')
    assert scengen.num_satellites == 1
    assert scengen.satellites[0].satcat_id == '25544'

# Allow this test to fail
@pytest.mark.xfail(reason="This test will fail is the number of satellites in the test constellation changes")
def test_add_constellation():
    scengen = ScenarioGenerator()

    assert scengen.num_satellites == 0

    scengen.add_constellation('CAPELLA')
    # This test might break if the constellation launches more satellites or if some decay
    assert scengen.num_satellites == 5

