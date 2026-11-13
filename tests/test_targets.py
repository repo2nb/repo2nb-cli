from repo2nb.targets import colab, kaggle


def test_kaggle_workspace_requires_no_git_auth(tmp_path):
    assert kaggle.auth_cells(tmp_path) == []
    cells = kaggle.workspace_cells()
    assert "repo2nb sync" in cells[0].source
    assert "kaggle kernels push" in cells[0].source
    assert cells[1].cell_type == "code"
    assert cells[1].source == ""
    assert not any("GITHUB_TOKEN" in c.source or "!git" in c.source for c in cells)


def test_get_remote_url(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    config = git_dir / "config"
    config.write_text('[remote "origin"]\n\turl = https://github.com/myuser/myrepo.git\n')

    url = colab._get_remote_url(tmp_path)
    assert url == "myuser/myrepo.git"


def test_colab_auth_uses_colab_api(tmp_path):
    cells = colab.auth_cells(tmp_path)

    remote_code = cells[2].source
    assert "google.colab import userdata" in remote_code
    assert "userdata.get" in remote_code
    assert "kaggle_secrets" not in remote_code

    tutorial = cells[0].source
    assert "Secrets" in tutorial and "sidebar" in tutorial.lower()
    assert "Add-ons" not in tutorial


def test_collapse_metadata():
    assert kaggle.collapse_metadata() == {"jupyter": {"source_hidden": True}}
    assert colab.collapse_metadata() == {"cellView": "form"}
