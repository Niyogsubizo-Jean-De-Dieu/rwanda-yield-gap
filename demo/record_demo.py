"""
Record demo/demo.webm: a guided walk through the dashboard (about 2 minutes, under the 3-minute limit).

    python3 -m pip install playwright && python3 -m playwright install chromium
    python3 demo/record_demo.py              # records the local dashboard in docs/
    python3 demo/record_demo.py https://<user>.github.io/<repo>/    # or the published one

You can also record yourself with a screen recorder (e.g. Screencastify) and save as demo/demo.webm.
"""
import asyncio
import shutil
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = sys.argv[1] if len(sys.argv) > 1 else (ROOT / "docs" / "index.html").as_uri()
OUT = ROOT / "demo" / "demo.webm"


async def caption(pg, text):
    """Show a short on-screen caption so the video explains itself without sound."""
    await pg.evaluate("""t => { let c = document.getElementById('demo-cap');
      if (!c) { c = document.createElement('div'); c.id = 'demo-cap';
        c.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:99;background:#17231c;color:#fff;font:600 18px/1.35 sans-serif;padding:10px 18px;border-radius:10px;max-width:80%;text-align:center;box-shadow:0 4px 16px rgba(0,0,0,.25)';
        document.body.appendChild(c); }
      c.textContent = t; }""", text)


async def main():
    tmp = ROOT / "demo" / "_video"
    shutil.rmtree(tmp, ignore_errors=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1280, "height": 760}, record_video_dir=str(tmp),
                                  record_video_size={"width": 1280, "height": 760})
        pg = await ctx.new_page()
        sel = lambda s, v: pg.select_option(s, v)
        wait = pg.wait_for_timeout
        await pg.goto(URL + ("#recommend" if "#" not in URL else ""))
        await wait(1500)
        await caption(pg, "Rwanda Yield Gap Explorer: NISR survey + satellite data, 30 districts, 2017 to 2025")
        await wait(4000)
        await caption(pg, "Recommendations: the input each district should promote, with priority and extra tonnes")
        await wait(5000)
        await pg.click("section.view:not([hidden]) .tile[data-d='Kirehe']"); await wait(3000)
        await sel("#f-crop", "Irish potato"); await wait(3500)
        await caption(pg, "National top 10 actions across all crops, and a summary by province")
        await pg.mouse.wheel(0, 900); await wait(5000)
        await pg.mouse.wheel(0, -900)
        await sel("#f-crop", "Maize"); await sel("#f-district", "Nyagatare")
        await pg.click("a[data-tab='trends']"); await wait(1500)
        await caption(pg, "Trends: NISR published yields from the baseline year, the district vs the national average, and the PSTA 5 target")
        await wait(5000)
        await sel("#f-district", "Kirehe"); await wait(2500)
        await sel("#f-base", "2019"); await wait(2500)
        await caption(pg, "Click any district on the map to select it")
        await pg.click("section.view:not([hidden]) .tile[data-d='Musanze']"); await wait(3000)
        await caption(pg, "Input use from the survey microdata: fertilizer, improved seed, manure")
        await pg.mouse.wheel(0, 700); await wait(4500)
        await pg.mouse.wheel(0, -700)
        await sel("#f-crop", "Maize"); await sel("#f-district", "Nyagatare")
        await pg.click("a[data-tab='scenarios']"); await wait(1500)
        await caption(pg, "Scenarios: what if farmers who do not use an input adopted it?")
        await wait(4500)
        for lever in ["fertilizer", "improved_seed", "manure", "package_fert_seed_manure"]:
            await pg.click(f"button[data-lever='{lever}']"); await wait(2500)
        await caption(pg, "Current vs attainable yield and extra tonnes, by district")
        await pg.mouse.wheel(0, 420); await wait(5000)
        await caption(pg, "Fertilizer dose-response and the top target districts, flagged as priority")
        await pg.mouse.wheel(0, 650); await wait(5000)
        await pg.mouse.wheel(0, -1100)
        await pg.click("a[data-tab='drivers']"); await wait(1500)
        await caption(pg, "What drives yield: SHAP explanation of the model, by crop")
        await wait(4000)
        await sel("#f-crop", "Climbing bean"); await wait(3500)
        await pg.click("a[data-tab='model']"); await wait(1500)
        await caption(pg, "Model reliability: tested on unseen districts, an unseen year, and season by season")
        await wait(4500)
        await pg.mouse.wheel(0, 500); await wait(4000)
        await pg.mouse.wheel(0, -500)
        await caption(pg, "Available in Kinyarwanda")
        await pg.click("#lang-rw"); await pg.click("a[data-tab='scenarios']"); await wait(5000)
        await pg.click("#lang-en"); await pg.click("a[data-tab='about']"); await wait(1000)
        await caption(pg, "Method, data sources, limitations and AI-use disclosure")
        await wait(4500)
        video = pg.video
        await ctx.close(); await b.close()
        OUT.unlink(missing_ok=True)
        Path(await video.path()).rename(OUT)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Saved {OUT}")


asyncio.run(main())
