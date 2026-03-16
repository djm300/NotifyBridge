from pathlib import Path


def test_docker_files_exist():
    assert Path("Dockerfile").exists()
    assert Path("docker-compose.yml").exists()
    assert Path("README.md").exists()
