import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PagesDeploymentTest(unittest.TestCase):
    def test_static_assets_are_relative_to_the_project_path(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('href="./styles.css', html)
        self.assertIn('src="./app.js', html)
        self.assertIn('href="./data/market-history.csv"', html)
        self.assertIn("fetch(`./data/dashboard.json", script)

    def test_pages_mode_hides_server_only_refresh(self) -> None:
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("location.hostname.endsWith('.github.io')", script)
        self.assertIn("refreshButton.hidden = true", script)
        self.assertIn("refreshButton.addEventListener('click', refreshData)", script)
        self.assertIn("[hidden] { display: none !important; }", styles)

    def test_workflow_builds_data_before_deploying(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("python3 -m unittest discover -s tests -v", workflow)
        self.assertIn("python3 app.py update --from 2020", workflow)
        self.assertIn("python3 app.py export", workflow)
        self.assertIn("actions/upload-pages-artifact@v4", workflow)
        self.assertIn("actions/deploy-pages@v4", workflow)
        self.assertIn('timezone: "Asia/Shanghai"', workflow)


if __name__ == "__main__":
    unittest.main()
