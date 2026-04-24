from ajas.config import settings
from ajas.logger import log


def test_imports():
    assert settings is not None
    assert log is not None
    log.info("Skeleton imports clean.")


if __name__ == "__main__":
    test_imports()
    print("All imports successful!")
