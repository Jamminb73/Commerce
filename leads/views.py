import os
import time
import random
import re
import urllib.parse
import json

# Force Django to allow database operations inside Playwright's loop context
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.core.management.base import BaseCommand
from playwright.sync_api import sync_playwright
from nameparser import HumanName

# 🛡️ IMPORT MATRIX MAP: Maps directly to your local application structure
from leads.models import ChamberLead, ChamberDirectory, ChamberRequest, Order, OrderItem, UserPurchase

# 🛡️ REFACTORED EXTRACTION FILTER MATRIX (Removed 'board of directors' and 'foundation' blockages)
BLACKLIST_KEYWORDS = (
    'camping', 'toll', 'road', 'download', 'pdf', 'excel', 'word', 'powerpoint',
    'trip', 'guide', 'visit', 'follow us', 'our mission', 'privacy policy', 
    'terms of service', 'newsletter', 'copyright', 'explore', 'vacation', 
    'listing', 'advertisement', 'heritage', 'gallery', 'history'
)

GENERIC_BOXES = ('info@', 'support@', 'admin@', 'marketing@', 'contact@', 'webmaster@', 'help@', 'membership@', 'events@', 'join@', 'chamber@', 'frontdesk@', 'sales@')

ORGANIZATION_KEYWORDS = (
    'business', 'center', 'visitor', 'council', 'service', 'chamber', 'association',
    'alliance', 'bureau', 'corporation', 'company', 'inc.', 'llc', 'group', 'dept',
    'department', 'practices', 'committee', 'development', 'partnership', 'network', 
    'agency', 'institute', 'society', 'club'
)


def is_valid_human_name(name_str):
    """Rigorously validates if a string is structured like an actual human name."""
    if not name_str:
        return False
        
    clean_str = name_str.strip()
    if len(clean_str) < 3 or len(clean_str) > 45 or "@" in clean_str:
        return False
        
    lower_str = clean_str.lower()
    if lower_str in ['read bio', 'view profile', 'staff', 'team', 'directory', 'members', 'home']:
        return False
        
    if any(keyword in lower_str for keyword in ORGANIZATION_KEYWORDS):
        return False

    words = clean_str.split()
    if len(words) < 2 or len(words) > 4:
        return False
        
    if not re.match(r"^[a-zA-Z\s\.\,\-\'’]+$", clean_str):
        return False

    try:
        parsed = HumanName(clean_str)
        if not parsed.first or not parsed.last:
            return False
    except Exception:
        return False
        
    return True


def parse_name(raw_name):
    """Splits full names cleanly into First and Last using nameparser properties."""
    clean_name = re.sub(r'[\s,]+(CEO|President|CPA|CCE|MBA|PC|Executive).*$', '', raw_name, flags=re.IGNORECASE).strip()
    if not is_valid_human_name(clean_name):
        return "", ""
    parsed = HumanName(clean_name)
    return parsed.first.strip(), parsed.last.strip()


class Command(BaseCommand):
    help = 'Runs the Playwright proximity scraper to collect Chamber leads entirely in memory.'

    def add_arguments(self, parser):
        parser.add_argument('--url', type=str, help='Target URL to scrape directly')
        parser.add_argument('--name', type=str, help='Custom Chamber Name')
        parser.add_argument('--state', type=str, help='Target State Focus')

    def handle(self, *args, **options):
        target_url = options.get('url')
        custom_name = options.get('name')
        target_state = options.get('state')

        session_results_manifest = {}

        if target_url and custom_name:
            self.stdout.write(self.style.SUCCESS(f"🚀 Routing Dynamic Target Pipeline Execution for {custom_name}..."))
            staged_leads, dynamic_url = self.refactored_chamber_scoper(target_url, custom_name)
            
            session_results_manifest[custom_name] = {
                'directory_url': dynamic_url or target_url,
                'state': target_state if target_state else 'US',
                'leads': staged_leads
            }
        else:
            chamber_market = [
                ('https://metroatlantachamber.com/meet-the-team/', 'Metro Atlanta Chamber', 'GA'),
                ('https://cobbchamber.org/about-us/chamber-staff/', 'Cobb Chamber', 'GA'),
                ('https://www.gwinnettchamber.org/staff/', 'Gwinnett Chamber', 'GA')
            ]
            
            self.stdout.write(self.style.SUCCESS("🚀 Starting Standard Chamber Pipeline Pure Memory Scraper..."))

            for url, name, state in chamber_market:
                staged_leads, dynamic_url = self.refactored_chamber_scoper(url, name)
                session_results_manifest[name] = {
                    'directory_url': dynamic_url or url,
                    'state': state,
                    'leads': staged_leads
                }
                time.sleep(random.uniform(2.0, 4.0))

        self.stdout.write(self.style.SUCCESS("\n🎉 Done! Proximity staging extraction finished."))
        
        for chamber, metrics in session_results_manifest.items():
            self.stdout.write(f"📊 Preview Ready: {chamber} ({len(metrics['leads'])} Staged Vectors Compiled). Payment Status: Pending.")
            
        return json.dumps(session_results_manifest)

    def discover_chamber_url(self, page, google_url):
        """🔍 Sifter Layer: Opens Google, handles consent gates, and pulls back organic results."""
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
        """🕷️ Intent Scout Layer: Scores navigation text semantically to locate high-value rosters."""
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            
            target_page = page.evaluate('''() => {
                let anchors = Array.from(document.querySelectorAll('a'));
                let bestLink = null;
                let highestScore = -999;

                let isValidLink = (a) => {
                    let hrefAttr = a.getAttribute('href') || '';
                    return hrefAttr.trim() !== '' && 
                           !hrefAttr.startsWith('#') && 
                           !hrefAttr.startsWith('javascript:') && 
                           a.href && 
                           a.href.startsWith('http');
                };

                // Semantic Priority Weights
                let scoringMatrix = [
                    { keywords: ['board of directors', 'board roster', 'governance'], score: 100 },
                    { keywords: ['chamber staff', 'meet the team', 'our team', 'staff directory'], score: 90 },
                    { keywords: ['staff', 'leadership', 'executive committee'], score: 80 },
                    { keywords: ['directory', 'about us', 'about-us', 'contact'], score: 40 }
                ];

                for (let anchor of anchors) {
                    if (!isValidLink(anchor)) continue;
                    
                    let text = (anchor.innerText || anchor.textContent || '').toLowerCase().trim();
                    let href = (anchor.getAttribute('href') || '').toLowerCase();
                    
                    let currentScore = 0;
                    let matchedAny = false;
                    
                    // Score based on text and href attributes
                    for (let rule of scoringMatrix) {
                        if (rule.keywords.some(kw => text.includes(kw) || href.includes(kw))) {
                            currentScore = Math.max(currentScore, rule.score);
                            matchedAny = true;
                        }
                    }

                    // 🌟 CRITICAL ANTI-PROGRAM SAFEGUARD: Heavily penalize landing page traps
                    if (text.includes('program') || href.includes('program') || text.includes('workshop') || href.includes('workshop')) {
                        currentScore -= 60;
                    }

                    if (matchedAny && currentScore > highestScore) {
                        highestScore = currentScore;
                        bestLink = anchor.href;
                    }
                }
                
                return bestLink;
            }''')
            
            if target_page:
                return target_page
        except Exception as e:
            self.stdout.write(f"⚠️ [SCOUT]: Navigation link scoring sweep hit an issue: {e}")
        return base_url

    def refactored_chamber_scoper(self, target_url, org_name):
        staged_json_payload = []
        resolved_url = target_url

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
                    resolved_url = self.crawl_for_directory_target(page, primary_domain)
                else:
                    self.stdout.write(self.style.ERROR("❌ [ENGINE ERROR]: Discovery link extraction failed."))
                    browser.close()
                    return staged_json_payload, resolved_url

            # 🎯 STAGE 1: Navigational Shift (Avoid member search widgets, hunt for human listings)
            if any(x in resolved_url.lower() for x in ["member-directory", "members", "directory"]):
                self.stdout.write(self.style.WARNING(f"⚠️ [PIVOT DETECTED]: Target path points to business listings. Scouting leadership targets..."))
                try:
                    page.goto(resolved_url, wait_until="domcontentloaded", timeout=30000)
                    rescue_url = page.evaluate('''() => {
                        let links = Array.from(document.querySelectorAll('a'));
                        let targets = ['board of directors', 'board', 'staff', 'team', 'leadership', 'governance', 'about us'];
                        for (let t of targets) {
                            let found = links.find(a => (a.innerText || a.textContent || '').toLowerCase().includes(t) && !a.href.includes('member-directory') && a.href.startsWith('http'));
                            if (found) return found.href;
                        }
                        return null;
                    }''')
                    if rescue_url:
                        resolved_url = rescue_url
                        self.stdout.write(self.style.SUCCESS(f"🔄 [RESCUE SUCCESS]: Redirected search route to high-signal layout: {resolved_url}"))
                except Exception:
                    pass

            for attempt in range(2):
                if attempt == 1:
                    parsed_uri = urllib.parse.urlparse(resolved_url)
                    fallback_base = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
                    self.stdout.write(self.style.WARNING(f"⚠️ [ZERO YIELD FALLBACK]: Attempt 1 hit an empty extraction layer. Retrying root routing map..."))
                    resolved_url = self.crawl_for_directory_target(page, fallback_base)

                self.stdout.write(f"⚙️ [PLAYWRIGHT]: (Attempt {attempt + 1}) Executing layout proximity scoper at: {resolved_url}")
                
                try:
                    page.goto(resolved_url, wait_until="domcontentloaded", timeout=45000)
                    time.sleep(5) 
                    
                    for _ in range(6):
                        page.evaluate("window.scrollBy(0, 800);")
                        time.sleep(0.4)
                    
                    extracted_leads = page.evaluate('''() => {
                        let data = [];
                        let seenEmails = new Set();
                        let emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/;
                        let junk = ["info@", "admin@", "events@", "support@", "frontdesk@", "sales@", "chamber@"];

                        // 1. Gather all raw anchor elements that have a mailto link
                        let mailtoAnchors = Array.from(document.querySelectorAll('a[href^="mailto:"]'));
                        
                        // Fallback: If no mailto tags exist, find elements whose text contains an email
                        if (mailtoAnchors.length === 0) {
                            let allElements = Array.from(document.querySelectorAll('body *')).filter(el => el.children.length === 0);
                            for (let el of allElements) {
                                let match = el.innerText ? el.innerText.match(emailRegex) : null;
                                if (match) {
                                    let mockAnchor = document.createElement('a');
                                    mockAnchor.setAttribute('href', 'mailto:' + match[0]);
                                    el.appendChild(mockAnchor);
                                    mailtoAnchors.push(mockAnchor);
                                }
                            }
                        }

                        // 2. Loop through every detected email anchor node
                        for (let anchor of mailtoAnchors) {
                            let email = anchor.getAttribute('href').replace('mailto:', '').split('?')[0].toLowerCase().trim();
                            if (seenEmails.has(email) || junk.some(word => email.includes(word))) continue;

                            let rawName = "";
                            let rawTitle = "";

                            // TIER 1: THE SMART CARD / CONTAINER SCOUT (Conquers Denver & Modern Grid Profiles)
                            let currentParent = anchor.parentElement;
                            let cardContainer = null;
                            for (let depth = 0; depth < 5; depth++) {
                                if (!currentParent || currentParent.tagName === 'BODY') break;
                                let className = (currentParent.className || '').toLowerCase();
                                let idName = (currentParent.id || '').toLowerCase();
                                
                                if (className.includes('card') || className.includes('member') || className.includes('staff') || 
                                    className.includes('team') || className.includes('profile') || className.includes('row') || 
                                    className.includes('block') || className.includes('item') || idName.includes('user')) {
                                    cardContainer = currentParent;
                                    break;
                                }
                                currentParent = currentParent.parentElement;
                            }

                            if (cardContainer) {
                                let cardTextNodes = Array.from(cardContainer.querySelectorAll('*'))
                                    .filter(el => el.children.length === 0)
                                    .map(el => (el.innerText || el.textContent).trim())
                                    .filter(txt => txt.length > 1 && !emailRegex.test(txt) && !txt.toLowerCase().includes('bio') && !txt.toLowerCase().includes('profile'));

                                if (cardTextNodes.length >= 2) {
                                    rawName = cardTextNodes[0];  
                                    rawTitle = cardTextNodes[1]; 
                                }
                            }

                            // TIER 2: REFINE BACKWARD PROXIMITY FALLBACK (Protects Atlanta & Legacy Flat Layouts)
                            if (!rawName || rawName.length < 3) {
                                let allLeafs = Array.from(document.querySelectorAll('body *')).filter(el => el.children.length === 0);
                                let idx = allLeafs.indexOf(anchor);
                                if (idx === -1) {
                                    idx = allLeafs.findIndex(el => el.contains(anchor) || anchor.contains(el));
                                }

                                if (idx !== -1) {
                                    let lookbackCount = 0;
                                    for (let j = idx - 1; j >= 0 && lookbackCount < 5; j--) {
                                        let text = (allLeafs[j].innerText || allLeafs[j].textContent).trim();
                                        if (!text || text.length < 2 || emailRegex.test(text) || /\\d{3}/.test(text) || text.toLowerCase().includes("bio")) continue;
                                        
                                        if (!rawTitle) {
                                            rawTitle = text;
                                        } else if (!rawName && text !== rawTitle) {
                                            rawName = text;
                                            break; 
                                        }
                                        lookbackCount++;
                                    }
                                }
                            }

                            if (rawName && rawName.length >= 3) {
                                seenEmails.add(email);
                                data.push({
                                    rawName: rawName,
                                    title: rawTitle || "Chamber Executive",
                                    email: email
                                });
                            }
                        }
                        return data;
                    }''')

                    seen_names = set()

                    for lead in extracted_leads:
                        raw_name = lead['rawName'].strip()
                        title = lead['title'].strip()
                        email = lead['email'].strip()

                        lower_name = raw_name.lower()
                        lower_title = title.lower()

                        if any(keyword in lower_name or keyword in lower_title for keyword in BLACKLIST_KEYWORDS):
                            continue

                        if any(bad in lower_name for bad in ["chamber", "home", "about", "events", "contact", "join", "sign up", "terms", "privacy"]):
                            continue

                        if email in title:
                            title = title.replace(email, "").strip()

                        first_name, last_name = parse_name(raw_name)
                        full_name = f"{first_name} {last_name}".strip()
                        
                        if not first_name or len(first_name) < 2 or full_name in seen_names:
                            continue
                        seen_names.add(full_name)

                        cleaned_title = title.strip().strip('-').strip(',').replace("  ", " ")
                        if not cleaned_title or cleaned_title.lower() in ["read bio", "view profile", "bio"]:
                            cleaned_title = "Chamber Executive"

                        staged_json_payload.append({
                            'first_name': first_name.strip().title(),
                            'last_name': last_name.strip().title(),
                            'title': cleaned_title,
                            'email': email.lower().strip()
                        })
                        self.stdout.write(f"   ⏳ Staged candidate memory structure: {first_name.title()} {last_name.title()} ({email})")

                    if len(staged_json_payload) > 0:
                        self.stdout.write(self.style.SUCCESS(f"   🔒 Compiled {len(staged_json_payload)} temporary lead vectors securely in-memory."))
                        break 
                    else:
                        self.stdout.write(self.style.WARNING(f"   ⚠️ Proximity extraction attempt hit 0 targets on current path."))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Execution crash on {org_name}: {e}"))
                    
            browser.close()

        return staged_json_payload, resolved_url