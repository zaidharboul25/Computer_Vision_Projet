"""Script de capture d'écran automatisé pour la Phase 2 (Playwright).

Respecte l'exigence 8 : identifiants lus dans E2E_USER et E2E_PASSWORD (variables d'environnement).
"""
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = Path("docs/screenshots/phase2")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

E2E_USER = os.environ.get("E2E_USER", "demo_operator")
E2E_PASSWORD = os.environ.get("E2E_PASSWORD")

if not E2E_PASSWORD:
    raise ValueError("La variable d'environnement E2E_PASSWORD doit être définie pour exécuter les captures Playwright.")

DEMO_INSPECTION_ID = "c4fefc27-2ceb-4778-a330-e5685296d34e"
ZERO_DEFECT_ID = "demo-zero-defects-0001"

def capture():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        page = context.new_page()

        # Connexion
        print("Connexion avec E2E_USER...")
        page.goto("http://localhost:5173/login")
        page.fill("input[name='username']", E2E_USER)
        page.fill("input[name='password']", E2E_PASSWORD)
        page.click("button[type='submit']")
        page.wait_for_selector("text=Tableau de bord WeaveGuard AI", timeout=10000)

        # 1. Page de nouvelle inspection (formulaire vierge)
        print("1. Capture de la page nouvelle inspection (formulaire vierge)...")
        page.goto("http://localhost:5173/inspections/new")
        page.wait_for_selector("text=Nouvelle inspection textile")
        time.sleep(1)
        page.screenshot(path=str(SCREENSHOTS_DIR / "01_new_inspection_form.png"))

        # 2. Page de nouvelle inspection avec image sélectionnée (prévisualisation locale)
        print("2. Capture avec prévisualisation locale de cliché textile...")
        sample_img = Path("docs/screenshots/phase1/01_login.png")
        if sample_img.exists():
            file_input = page.locator("input[data-testid='file-input']")
            file_input.set_input_files(str(sample_img.resolve()))
            page.locator("img[alt*='textile']").wait_for(timeout=5000)
            time.sleep(1)
            page.screenshot(path=str(SCREENSHOTS_DIR / "02_new_inspection_preview.png"))

        # 3. Résultat d'inspection avec détections réelles et télémétrie moteurs
        print("3. Capture du résultat d'inspection (données réelles démo)...")
        page.goto(f"http://localhost:5173/inspections/{DEMO_INSPECTION_ID}")
        page.wait_for_selector("text=Progression et télémétrie des moteurs")
        page.wait_for_selector("text=Visualisation des couches")
        page.wait_for_selector("text=Export JSON (AC-04)")
        time.sleep(2)
        page.screenshot(path=str(SCREENSHOTS_DIR / "03_inspection_result_demo.png"))

        # 4. État contractuel "Aucune région détectée"
        print("4. Capture de l'état 'Aucune région détectée'...")
        page.goto(f"http://localhost:5173/inspections/{ZERO_DEFECT_ID}")
        page.wait_for_selector("text=Aucune région détectée par les moteurs exécutés")
        page.wait_for_selector("text=Ce résultat n'est pas une garantie d'absence de défaut")
        time.sleep(1.5)
        page.screenshot(path=str(SCREENSHOTS_DIR / "04_inspection_zero_regions.png"))

        browser.close()
        print("Toutes les captures d'écran Phase 2 ont été générées avec succès dans docs/screenshots/phase2/.")

if __name__ == "__main__":
    capture()
