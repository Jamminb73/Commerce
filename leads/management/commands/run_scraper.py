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

    def add_arguments(self, parser):
        """Allows optional targeting parameters to be passed in from command line or views."""
        parser.add_argument('--url', type=str, help='Target URL to scrape directly')
        parser.add_argument('--name', type=str, help='Custom Chamber Name')
        parser.add_argument('--state', type=str, help='Target State Focus')

    def handle(self, *args, **options):
        target_url = options.get('url')
        custom_name = options.get('name')
        target_state = options.get('state')

        if target_url and custom_name:
            self.stdout.write(self.style.SUCCESS(f"🚀 Routing Dynamic Target Pipeline Execution for {custom_name}..."))
            
            # Create a clean base object framework
            directory_obj, _ = ChamberDirectory.objects.get_or_create(
                name=custom_name,
                defaults={
                    'state': target_state if target_state else 'US',
                    'directory_url': target_url,
                    'is_active': True
                }
            )
            
            # Run our unified dynamic scoper loop
            self.refactored_chamber_scoper(target_url, custom_name, directory_obj)
            
        else:
            # 🔄 FALLBACK ROUTE: Run default market assets if no args specified (Terminal Mode)
            chamber_market = [
                ('https://metroatlantachamber.com/meet-the-team/', 'Metro Atlanta Chamber', 'GA'),
                ('https://cobbchamber.org/about-us/chamber-staff/', 'Cobb Chamber', 'GA'),
                ('https://www.gwinnettchamber.org/staff/', 'Gwinnett Chamber', 'GA')
            ]
            
            self.stdout.write(self.style.SUCCESS("🚀 Starting Standard Chamber Pipeline Database Scraper..."))

            for url, name, state in chamber_market:
                directory_obj, _ = ChamberDirectory.objects.get_or_create(
                    name=name,
                    defaults={
                        'state': state,
                        'directory_url': url,
                        'is_active': True
                    }
                )
                self.refactored_chamber_scoper(url, name, directory_obj)
                time.sleep(random.uniform(2.0, 4.0))

        self.stdout.write(self.style.SUCCESS("\n🎉 Done! Proximity database sync completely finished."))

    def discover_chamber_url(self, page, google_url):
        """🔍 Sifter Layer: Opens Google, dodges ad headers, and pulls back the top organic result."""
        self.stdout.write("🔍 [DISCOVERY]: Intercepting fallback URL... Scanning Google Search nodes...")
        try:
            page.goto(google_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            
            # Pull all anchor references from the search results grid
            links = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('a'))
                    .map(a => a.href)
                    .filter(href => href && href.startsWith('http') && !href.includes('google.com'));
            }''')
            
            for link in links:
                # Bypass maps, search terms, or cookie policies
                if any(x in link.lower() for x in ['search?', 'maps.', 'support.', 'accounts.']):
                    continue
                self.stdout.write(f"🔗 [DISCOVERY]: Sourced primary domain authority: {link}")
                return link
        except Exception as e:
            self.stdout.write(f"⚠️ [DISCOVERY]: Sifter index time out or mismatch: {e}")
        return None

    def crawl_for_directory_target(self, page, base_url):
        """🕷️ Scout Layer: Crawls internal navigation menus to jump straight to team/staff pages."""
        self.stdout.write("🕷️ [SCOUT]: Sifting internal nav mapping layout for contact targets...")
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            
            # Hunt through all text properties for structural terms
            target_page = page.evaluate('''() => {
                let anchors = Array.from(document.querySelectorAll('a'));
                let keywords = ['staff', 'team', 'about-us', 'directory', 'about/staff', 'about/team', 'contact-us'];
                
                // First pass: Check actual link text strings matches
                for (let kw of keywords) {
                    let match = anchors.find(a => (a.innerText || a.textContent || '').toLowerCase().includes(kw));
                    if (match && match.href && match.href.startsWith('http')) return match.href;
                }
                
                // Second pass: Sift through raw href strings attributes
                for (let kw of keywords) {
                    let match = anchors.find(a => (a.getAttribute('href') || '').toLowerCase().includes(kw));
                    if (match && match.href && match.href.startsWith('http')) return match.href;
                }
                return null;
            }''')
            
            if target_page:
                self.stdout.write(f"🎯 [SCOUT]: Automated routing locked onto index page: {target_page}")
                return target_page
        except Exception as e:
            self.stdout.write(f"⚠️ [SCOUT]: Navigation map scan incomplete: {e}")
        return base_url

    def refactored_chamber_scoper(self, target_url, org_name, directory_obj):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # 💡 DISCOVERY ENGAGEMENT STEP: Check if we are running an on-demand background search route
            if "google.com/search" in target_url:
                primary_domain = self.discover_chamber_url(page, target_url)
                if primary_domain:
                    # Update our target URL coordinates dynamically to use the real company asset link
                    target_url = self.crawl_for_directory_target(page, primary_domain)
                    
                    # Update your directory record in the database so it's clean for future customer store entries
                    directory_obj.directory_url = target_url
                    directory_obj.save()
                else:
                    self.stdout.write(self.style.ERROR("❌ [ENGINE ERROR]: Discovery was unable to extract an authoritative domain link."))
                    browser.close()
                    return

            self.stdout.write(f"⚙️ [PLAYWRIGHT]: Executing proximity lookup parse at: {target_url}")
            
            try:
                # 🚀 STABILITY TWEAK: Using domcontentloaded stops network-idle tracker hang crashes cold!
                page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
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