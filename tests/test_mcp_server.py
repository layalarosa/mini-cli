from mcp_server import PROJECT_ROOT, fetch_url, list_files, resolve_project_path


def test_list_files_allows_project_root():
    assert "mcp_server.py" in list_files(".")


def test_list_files_rejects_path_outside_project():
    result = list_files("..")
    assert "dentro del directorio del proyecto" in result


def test_resolve_project_path_keeps_relative_paths_inside_root():
    assert resolve_project_path("docs").is_relative_to(PROJECT_ROOT)


def test_fetch_url_rejects_local_network_addresses():
    assert "deshabilitada" in fetch_url("http://127.0.0.1:11434")
