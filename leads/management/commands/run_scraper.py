import os
import time
import random
import re
import urllib.parse

# Force Django to allow database operations inside Playwright's loop context
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.core.management.base import BaseCommand
from playwright.sync_api import sync_playwright
from leads.models import ChamberLead, ChamberDirectory 

# 🛡️ THE HIGH-FIDELITY EXTRACTION FILTER MATRIX
BLACKLIST_KEYWORDS = (
    'camping', 'toll', 'road', 'download', 'pdf', 'excel', 'word', 'powerpoint',
    'trip', 'guide', 'visit', 'follow us', 'our mission', 'privacy policy', 
    'terms of service', 'about us', 'contact us', 'newsletter', 'copyright',
    'explore', 'vacation', 'listing', 'advertisement', 'heritage', 'gallery',
    'board of directors', 'executive committee', 'history', 'foundation'
)

# Hard exclusion patterns for structural mailboxes
GENERIC_BOXES = ('info@', 'support@', 'admin@', 'marketing@', 'contact@', 'webmaster@', 'help@', 'membership@', 'events@', 'join@', 'chamber@', 'frontdesk@', 'sales@')


def is_valid_human_name(name_str):
    """
    Validates if a string is structured like a reasonable human name.
    Filters out navigation text, layout structures, and lone words.
    """
    if not name_str:
        return False
        
    clean_str = name_str.strip()
    
    # Quick structural check: reject long strings, empty strings, or strings with emails
    if len(clean_str) < 3 or len(clean_str) > 35 or "@" in clean_str:
        return False
        
    # Block structural patterns or common single words acting as headers
    lower_str = clean_str.lower()
    if lower_str in ['read bio', 'view profile', 'staff', 'team', 'directory', 'board', 'executive', 'members', 'home']:
        return False
        
    # Check word counts: Human directory names are typically 2 to 3 words
    words = clean_str.split()
    if len(words) < 2 or len(words) > 3:
        return False
        
    # Regex check: Ensure the string only contains valid alphabetic characters, spaces, hyphens, and apostrophes
    if not re.match(r"^[a-zA-Z\s\.\-\'’]+$", clean_str):
        return False
        
    return True


def parse_name(raw_name):
    """Splits full names cleanly into First and Last, handling middle initials."""
    if not is_valid_human_name(raw_name):
        return "", ""

    parts = raw_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    elif len(parts) == 2:
        return parts[0], parts[1]
    else:
        # Gracefully handle middle initials/names by mapping to First and Last bounds
        return parts[0], parts[-1]


class Command(BaseCommand):
    help = 'Runs the Playwright proximity scraper to collect Chamber leads directly into the database.'

    def add_arguments(self, parser):
        parser.add_argument('--url', type=str, help='Target URL to scrape directly')
        parser.add_argument('--name', type=str, help='Custom Chamber Name')
        parser.add_argument('--state', type=str, help='Target State Focus')

    def handle(self, *args, **options):
        target_url = options.get('url')
        custom_name = options.get('name')
        target_state = options.get('state')

        if target_url and custom_name:
            self.stdout.write(self.style.SUCCESS(f"🚀 Routing Dynamic Target Pipeline Execution for {custom_name}..."))
            
            directory_obj, _ = ChamberDirectory.objects.get_or_create(
                name=custom_name,
                defaults={
                    'state': target_state if target_state else 'US',
                    'directory_url': target_url,
                    'is_active': True
                }
            )
            self.refactored_chamber_scoper(target_url, custom_name, directory_obj)
            
        else:
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
        """🔍 Sifter Layer: Opens Google, handles consent gates, and pulls back organic results."""
        self.stdout.write("🔍 [DISCOVERY]: Intercepting fallback URL... Scanning Google Search nodes...")
        try:
            page.goto(google_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            
            consent_handled = page.evaluate('''() => {
                let buttons = Array.from(document.querySelectorAll('button, div[role="button"]'));
                let targets = ['accept all', 'i agree', 'agree', 'accept', 'allow all'];
                for (let btn of buttons) {
                    let text = (btn.innerText || btn.textContent || '').toLowerCase().trim();
                    if (targets.includes(text)) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }''')
            
            if consent_handled:
                self.stdout.write("🛡️ [DISCOVERY]: Bypassed Google Cookie Gate. Waiting for search canvas re-render...")
                time.sleep(3)

            links = page.evaluate('''() => {
                let results = [];
                let anchors = Array.from(document.querySelectorAll('a'));
                for (let a of anchors) {
                    let href = a.href;
                    let text = (a.innerText || a.textContent || '').toLowerCase();
                    if (!href) continue;
                    if (href.includes('google.com/url?')) {
                        let match = href.match(/[?&]q=([^&]+)/);
                        if (match) href = decodeURIComponent(match[1]);
                    }
                    if (href.startsWith('http') && !href.includes('google.com')) {
                        results.push({ href: href, text: text });
                    }
                }
                return results;
            }''')
            
            if len(links) == 0:
                match = re.search(r'q=([^&]+)', google_url)
                if match:
                    query = re.sub(r'\+|-', ' ', urllib.parse.unquote(match[1]))
                    clean_query = query.lower().replace('chamber of commerce', '').replace('chamber', '').strip()
                    clean_query = re.sub(r'\b(ca|ga|fl|ny|tx|nc|sc|oh|il|city|regional)\b', '', clean_query).strip()
                    domain_guess = clean_query.replace(' ', '')
                    return f"https://www.{domain_guess}chamber.org"

            for node in links:
                link = node['href']
                text = node['text']
                if any(x in link.lower() for x in ['search?', 'maps.', 'support.', 'accounts.', 'googleusercontent', 'preferences']):
                    continue
                if 'chamber' in link.lower() or 'chamber' in text or 'commerce' in text:
                    return link
                    
            for node in links:
                link = node['href']
                if any(x in link.lower() for x in ['search?', 'maps.', 'support.', 'accounts.', 'googleusercontent', 'preferences']):
                    continue
                return link
        except Exception as e:
            self.stdout.write(f"⚠️ [DISCOVERY]: Sifter index time out: {e}")
        return None

    def crawl_for_directory_target(self, page, base_url):
        """🕷️ Scout Layer: Crawls internal navigation menus to jump straight to team/staff pages."""
        self.stdout.write("🕷️ [SCOUT]: Sifting internal nav mapping layout for contact targets...")
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            
            target_page = page.evaluate('''() => {
                let anchors = Array.from(document.querySelectorAll('a'));
                let keywords = ['staff', 'team', 'about-us', 'directory', 'about/staff', 'about/team', 'contact-us'];
                
                // Helper to ensure a link isn't a dead-end JavaScript trigger or empty hash
                let isValidLink = (a) => {
                    let hrefAttr = a.getAttribute('href') || '';
                    return hrefAttr.trim() !== '' && 
                           !hrefAttr.startsWith('#') && 
                           !hrefAttr.startsWith('javascript:') && 
                           a.href && 
                           a.href.startsWith('http');
                };

                // First pass: Check link text strings matches
                for (let kw of keywords) {
                    let match = anchors.find(a => (a.innerText || a.textContent || '').toLowerCase().includes(kw) && isValidLink(a));
                    if (match) return match.href;
                }
                
                // Second pass: Sift through raw href strings attributes
                for (let kw of keywords) {
                    let match = anchors.find(a => (a.getAttribute('href') || '').toLowerCase().includes(kw) && isValidLink(a));
                    if (match) return match.href;
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
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--disable-infobars', '--no-sandbox']
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True
            )
            page = context.new_page()
            
            if "google.com/search" in target_url:
                primary_domain = self.discover_chamber_url(page, target_url)
                if primary_domain:
                    target_url = self.crawl_for_directory_target(page, primary_domain)
                    directory_obj.directory_url = target_url
                    directory_obj.save()
                else:
                    self.stdout.write(self.style.ERROR("❌ [ENGINE ERROR]: Discovery link extraction failed."))
                    browser.close()
                    return

            self.stdout.write(f"⚙️ [PLAYWRIGHT]: Executing targeted element micro-scoping at: {target_url}")
            
            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(5) 
                
                for _ in range(6):
                    page.evaluate("window.scrollBy(0, 800);")
                    time.sleep(0.4)
                
                # 🔥 TARGETED ELEMENT MICRO-SCOPING PARSER 
                extracted_leads = page.evaluate('''() => {
                    let data = [];
                    let emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/;
                    
                    // Step 1: Locate high-probability DOM wrappers / Profile Card components
                    let containers = document.querySelectorAll(
                        'div[class*="staff"], div[class*="team"], div[class*="member"], div[class*="card"], ' +
                        'div[class*="profile"], tr, div[style*="grid"], div[class*="directory-item"], article'
                    );
                    
                    let checkedContainers = new Set();

                    containers.forEach(container => {
                        // Minimize nested duplicate execution sweeps
                        if (container.querySelectorAll('div[class*="card"], tr').length > 1) return;
                        
                        let htmlContext = container.innerHTML || '';
                        let textContext = (container.innerText || container.textContent || '').trim();
                        
                        // Look for a valid mailbox signature nested explicitly within this element bundle
                        let emailMatch = textContext.match(emailRegex);
                        let mailtoMatch = container.querySelector('a[href^="mailto:"]');
                        
                        if (emailMatch || mailtoMatch) {
                            let email = "";
                            if (mailtoMatch) {
                                email = mailtoMatch.getAttribute('href').replace('mailto:', '').split('?')[0].toLowerCase().trim();
                            } else if (emailMatch) {
                                email = emailMatch[0].toLowerCase().trim();
                            }

                            // Immediate Top-Level Gateway Mailbox Exclusions
                            let systemBoxes = ["info@", "admin@", "events@", "support@", "frontdesk@", "sales@", "chamber@", "membership@", "marketing@", "contact@", "join@"];
                            if (!email || systemBoxes.some(box => email.includes(box))) return;

                            // Extract text rows explicitly confined within this micro-scoped container
                            let textRows = textContext.split('\\n')
                                .map(r => r.trim())
                                .filter(r => r.length > 1 && !emailRegex.test(r) && !/\\d{3}/.test(r));

                            if (textRows.length >= 1) {
                                let potentialName = textRows[0];
                                let potentialTitle = textRows.length > 1 ? textRows[1] : "Chamber Executive";
                                
                                data.push({
                                    rawName: potentialName,
                                    title: potentialTitle,
                                    email: email
                                });
                                checkedContainers.add(container);
                            }
                        }
                    });

                    // Fallback Pass: If structural cards aren't matched, parse clean standard layout tables/headers
                    if (data.length === 0) {
                        let headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, strong'));
                        headings.forEach(h => {
                            let txt = (h.innerText || h.textContent || '').trim();
                            // Quick validation gate inside DOM evaluation context
                            if (txt && txt.length > 3 && txt.length < 30 && /^[a-zA-Z\\s\\.\\-\\'’]+$/.test(txt)) {
                                let words = txt.split(/\\s+/);
                                if (words.length >= 2 && words.length <= 3) {
                                    // Walk next elements to capture title properties safely
                                    let nextEl = h.nextElementSibling;
                                    let nextTxt = nextEl ? (nextEl.innerText || nextEl.textContent || '').trim() : '';
                                    if (nextTxt && nextTxt.length > 3 && nextTxt.length < 60 && !nextTxt.includes('\\n')) {
                                        data.push({ rawName: txt, title: nextTxt, email: "" });
                                    }
                                }
                            }
                        });
                    }
                    
                    return data;
                }''')

                parsed_uri = urllib.parse.urlparse(target_url)
                base_domain = parsed_uri.netloc.replace('www.', '')

                seen_names = set()
                records_saved = 0

                for lead in extracted_leads:
                    raw_name = lead['rawName'].strip()
                    title = lead['title'].strip()
                    email = lead['email'].strip()

                    lower_name = raw_name.lower()
                    lower_title = title.lower()
                    lower_email = email.lower()

                    # 🛡️ PIPELINE GATEWAY FILTERS: Drop system keywords or structural artifacts
                    if any(keyword in lower_name or keyword in lower_title for keyword in BLACKLIST_KEYWORDS):
                        continue

                    if any(lower_email.startswith(box) for box in GENERIC_BOXES):
                        continue

                    if any(bad in lower_name for bad in ["chamber", "home", "about", "events", "contact", "join", "sign up", "terms", "privacy", "staff"]):
                        continue

                    # Cleanse out email duplications embedded inside titles
                    if email in title:
                        title = title.replace(email, "").strip()

                    # Run rigorous Human Name validation patterns
                    first_name, last_name = parse_name(raw_name)
                    full_name = f"{first_name} {last_name}".strip()
                    
                    if not first_name or len(first_name) < 2 or full_name in seen_names:
                        continue
                        
                    seen_names.add(full_name)

                    cleaned_title = title.strip().strip('-').strip(',').replace("  ", " ")
                    if not cleaned_title or cleaned_title.lower() in ["read bio", "view profile", "bio"]:
                        cleaned_title = "Chamber Executive"

                    # 💎 FINESSE INTERPOLATION LAYER (If email wasn't harvested straight out of DOM container)
                    if not email:
                        first_initial = first_name[0].lower()
                        clean_last = last_name.lower().replace(" ", "").replace("-", "")
                        email = f"{first_initial}{clean_last}@{base_domain}"

                    # Re-verify interpolation results against catch-all gates
                    if any(email.lower().startswith(box) for box in GENERIC_BOXES):
                        continue

                    # Database Core Upsert Engine
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
                    status_msg = "Created candidate" if created else "Updated existing candidate"
                    self.stdout.write(f"   🎯 {status_msg}: {first_name.title()} {last_name.title()} - {cleaned_title} ({email})")

                if records_saved == 0:
                    self.stdout.write(self.style.WARNING(f"   ⚠️ Micro-scoping layer returned 0 records for {org_name}."))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Execution crash on {org_name}: {e}"))
                
            browser.close()