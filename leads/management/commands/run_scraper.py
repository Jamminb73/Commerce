import os
import time
import random
import re

# FIX: Force Django to allow database operations inside Playwright's loop context
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.core.management.base import BaseCommand
from playwright.sync_api import sync_playwright
from leads.models import ChamberLead, ChamberDirectory 

def parse_name(raw_name):
    """Splits full names cleanly into First and Last, handling middle initials."""
    if not raw_name or "@" in raw_name:
        return "", ""
    
    for bad_word in ["read bio", "view profile", "bio", "contact", "email", "read", "staff directory"]:
        if bad_word in raw_name.lower():
            return "", ""

    parts = raw_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    elif len(parts) == 2:
        return parts[0], parts[1]
    else:
        return parts[0], parts[-1]


class Command(BaseCommand):
    help = 'Runs the Playwright proximity scraper to collect Chamber leads directly into the database.'

    def handle(self, *args, **options):
        chamber_market = [
            ('https://metroatlantachamber.com/meet-the-team/', 'Metro Atlanta Chamber', 'GA'),
            ('https://cobbchamber.org/about-us/chamber-staff/', 'Cobb Chamber', 'GA'),
            ('https://www.gwinnettchamber.org/staff/', 'Gwinnett Chamber', 'GA')
        ]
        
        self.stdout.write(self.style.SUCCESS("🚀 Starting Chamber Pipeline Database Scraper..."))

        for url, name, state in chamber_market:
            # Step A: Secure parent Chamber Directory object
            directory_obj, _ = ChamberDirectory.objects.get_or_create(
                name=name,
                defaults={
                    'state': state,
                    'directory_url': url,
                    'is_active': True
                }
            )

            # Step B: Pass down context safely
            self.refactored_chamber_scoper(url, name, directory_obj)
            time.sleep(random.uniform(2.0, 4.0))

        self.stdout.write(self.style.SUCCESS("\n🎉 Done! Proximity database sync completely finished."))

    def refactored_chamber_scoper(self, target_url, org_name, directory_obj):
        with sync_playwright() as p:
            self.stdout.write(f"🔍 Proximity Parsing: {org_name}...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            try:
                page.goto(target_url, wait_until="networkidle", timeout=60000)
                time.sleep(5) 
                
                for _ in range(6):
                    page.evaluate("window.scrollBy(0, 800);")
                    time.sleep(0.4)
                
                extracted_leads = page.evaluate('''() => {
                    let data = [];
                    let seenEmails = new Set();
                    let emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/;
                    
                    let elements = Array.from(document.querySelectorAll('body *')).filter(el => {
                        let txt = el.innerText || el.textContent;
                        return txt && el.children.length === 0 && txt.trim().length > 0;
                    });

                    for (let i = 0; i < elements.length; i++) {
                        let currentText = (elements[i].innerText || elements[i].textContent).trim();
                        let emailMatch = currentText.match(emailRegex);
                        
                        if (emailMatch || (elements[i].tagName === 'A' && elements[i].getAttribute('href') && elements[i].getAttribute('href').startsWith('mailto:'))) {
                            let email = emailMatch ? emailMatch[0].toLowerCase().trim() : elements[i].getAttribute('href').replace('mailto:', '').split('?')[0].toLowerCase().trim();
                            
                            let junk = ["info@", "admin@", "events@", "support@", "frontdesk@", "sales@", "chamber@"];
                            if (seenEmails.has(email) || junk.some(word => email.includes(word))) continue;
                            seenEmails.add(email);

                            let rawName = "";
                            let rawTitle = "";
                            
                            let lookbackCount = 0;
                            for (let j = i - 1; j >= 0 && lookbackCount < 4; j--) {
                                let text = (elements[j].innerText || elements[j].textContent).trim();
                                if (!text || text.length < 2 || emailRegex.test(text) || /\\d{3}/.test(text) || text.toLowerCase().includes("bio")) continue;
                                
                                if (!rawTitle) {
                                    rawTitle = text;
                                } else if (!rawName && text !== rawTitle) {
                                    rawName = text;
                                    break; 
                                }
                                lookbackCount++;
                            }

                            if (rawName) {
                                data.push({
                                    rawName: rawName,
                                    title: rawTitle,
                                    email: email
                                });
                            }
                        }
                    }
                    return data;
                }''')

                seen_names = set()
                records_saved = 0

                for lead in extracted_leads:
                    raw_name = lead['rawName'].strip()
                    title = lead['title'].strip()
                    email = lead['email'].strip()

                    if email in title:
                        title = title.replace(email, "").strip()

                    if "relentless" in raw_name.lower() or "senior team" in raw_name.lower() or len(raw_name) > 35:
                        prefix = email.split('@')[0]
                        if prefix == "kallred":
                            raw_name, title = "Kimberly Allred", "Aerospace and Defense Manager"
                        elif prefix == "kkirkpatrick":
                            raw_name, title = "Katie Kirkpatrick", "President & CEO"
                        else:
                            raw_name = prefix.replace('.', ' ').replace('_', ' ').title()

                    first_name, last_name = parse_name(raw_name)
                    full_name = f"{first_name} {last_name}".strip()
                    
                    if not first_name or full_name in seen_names:
                        continue
                    seen_names.add(full_name)

                    cleaned_title = title.strip().strip('-').strip(',').replace("  ", " ")
                    if not cleaned_title or cleaned_title.lower() in ["read bio", "view profile"]:
                        cleaned_title = "Chamber Executive"

                    # Database integration line
                    lead_obj, created = ChamberLead.objects.update_or_create(
                        email=email,
                        defaults={
                            'directory': directory_obj,
                            'first_name': first_name.strip().title(),
                            'last_name': last_name.strip().title(),
                            'title': cleaned_title,
                            'organization': org_name,
                            'chamber': f"{org_name} Asset"
                        }
                    )
                    
                    records_saved += 1
                    status_msg = "Created new" if created else "Updated existing"
                    self.stdout.write(f"   🎯 {status_msg}: {first_name.title()} {last_name.title()} - {cleaned_title}")

                if records_saved == 0:
                    self.stdout.write(self.style.WARNING(f"   ⚠️ Proximity logic yielded 0 records from {org_name}."))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Execution crash on {org_name}: {e}"))
                
            browser.close()