"""Script de capture d'écran automatisé pour la Phase 1 (Playwright)."""
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = Path("docs/screenshots/phase1")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

E2E_USER = os.environ.get("E2E_USER", "demo_supervisor")
E2E_PASSWORD = os.environ.get("E2E_PASSWORD")
OPERATOR_USER = os.environ.get("OPERATOR_USER", "demo_operator")
OPERATOR_PASSWORD = os.environ.get("OPERATOR_PASSWORD")

def capture():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        page = context.new_page()

        # 1. Écran de connexion (Light)
        print("1. Capture de l'écran de connexion...")
        page.goto("http://localhost:5173/login")
        page.wait_for_selector("text=WeaveGuard")
        time.sleep(1)
        page.screenshot(path=str(SCREENSHOTS_DIR / "01_login.png"))

        # 2. Erreur d'authentification
        print("2. Capture de l'erreur d'authentification...")
        page.fill("input[name='username']", "demo_operator")
        page.fill("input[name='password']", "mauvais_mot_de_passe")
        page.click("button[type='submit']")
        page.wait_for_selector("text=Code : UNAUTHENTICATED")
        time.sleep(1)
        page.screenshot(path=str(SCREENSHOTS_DIR / "02_login_error.png"))

        # 3. Connexion réussie Superviseur -> Tableau de bord
        print("3. Capture du tableau de bord Superviseur...")
        page.fill("input[name='username']", E2E_USER)
        page.fill("input[name='password']", E2E_PASSWORD or "")
        page.click("button[type='submit']")
        page.wait_for_selector("text=Tableau de bord WeaveGuard AI")
        page.wait_for_selector("text=Inspections totales")
        time.sleep(1.5)
        page.screenshot(path=str(SCREENSHOTS_DIR / "03_dashboard_supervisor.png"))

        # 4. Mode Sombre (Dark Mode)
        print("4. Capture en mode sombre...")
        theme_btn = page.locator("button[aria-label*='Activer le mode sombre']")
        if theme_btn.count() > 0:
            theme_btn.click()
            time.sleep(0.5)
            page.screenshot(path=str(SCREENSHOTS_DIR / "04_dashboard_dark.png"))
            # Revenir en mode clair
            page.locator("button[aria-label*='Activer le mode clair']").click()
            time.sleep(0.5)

        # 5. Déconnexion puis test accès refusé (403)
        print("5. Capture accès refusé (403)...")
        page.click("button[title='Se déconnecter']")
        page.wait_for_selector("input[name='username']")
        page.fill("input[name='username']", "demo_operator")
        page.fill("input[name='password']", OPERATOR_PASSWORD or "")
        page.click("button[type='submit']")
        page.wait_for_selector("text=WeaveGuard AI")
        time.sleep(1)
        # Naviguer vers /admin
        page.goto("http://localhost:5173/admin")
        page.wait_for_selector("text=non autoris")
        time.sleep(1)
        page.screenshot(path=str(SCREENSHOTS_DIR / "05_forbidden_403.png"))

        browser.close()
        print("Captures d'écran terminées avec succès dans docs/screenshots/phase1/")

if __name__ == "__main__":
    capture()
