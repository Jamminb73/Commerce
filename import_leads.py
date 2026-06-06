import csv
from io import StringIO
from leads.models import ChamberLead  # Adjust 'leads' if your app name is different

# Your raw copied data block
csv_data = """First Name,Last Name,Title,Organization,Email,Phone,Extension,Avatar Image URL
Senior,Team,Katie Kirkpatrick,Metro Atlanta Chamber,kkirkpatrick@macoc.com,,,
Dcorso,,Dan Corso,Metro Atlanta Chamber,dcorso@macoc.com,,,
Kputnam,,Kathryn Putnam,Metro Atlanta Chamber,kputnam@macoc.com,,,
Dray,,Douglas Ray,Metro Atlanta Chamber,dray@macoc.com,,,
Jrys,,Janice Rys,Metro Atlanta Chamber,jrys@macoc.com,,,
Dwilliams,,Dave Williams,Metro Atlanta Chamber,dwilliams@macoc.com,,,
Jparrish,,Jerry Parrish,Metro Atlanta Chamber,jparrish@macoc.com,,,
Gyanis,,Georgia Yanis,Metro Atlanta Chamber,gyanis@macoc.com,,,
Kbrigman,,Kristi Brigman,Metro Atlanta Chamber,kbrigman@macoc.com,,,
Kimberly,Allred,Aerospace and Defense Manager,Metro Atlanta Chamber,kallred@macoc.com,,,
Jason,Barringer,Research Manager,Metro Atlanta Chamber,jbarringer@macoc.com,,,
Margaret,Beckley,"Manager, Community Relations",Metro Atlanta Chamber,asc@macoc.com,,,
Kate,Belson,Marketing Director,Metro Atlanta Chamber,kbelson@macoc.com,,,
Robbie,Boyles,Accounting Manager,Metro Atlanta Chamber,rboyles@macoc.com,,,
Kendall,Brantley,"Project Coordinator, Economic Development",Metro Atlanta Chamber,kbrantley@macoc.com,,,
Deidra,Brown,Payroll and Benefits Manager,Metro Atlanta Chamber,dbrown@macoc.com,,,
Leanna,Brown,"Vice President, Business Climate and Public Policy",Metro Atlanta Chamber,lbrown@macoc.com,,,
Tim,Cairl,"Vice President, Talent Development",Metro Atlanta Chamber,tcairl@macoc.com,,,
Lauren,Clarke,"Talent Coordinator, Georgia Intern App",Metro Atlanta Chamber,lclarke@macoc.com,,,
Alex,Conarton,Research Analyst,Metro Atlanta Chamber,aconarton@macoc.com,,,
Faith,Cox,Senior Project Coordinator,Metro Atlanta Chamber,fcox@macoc.com,,,
Clay,Cribbs,Social Media Marketing Manager,Metro Atlanta Chamber,ccribbs@macoc.com,,,
Cynthia,Curry,"Senior Director, Cleantech Ecosystem Expansion",Metro Atlanta Chamber,ccurry@macoc.com,,,
Julia,Davidson,"Vice President, Marketing",Metro Atlanta Chamber,jdavidson@macoc.com,,,
Megan,Dyer,"Manager, Public Policy & Strategy",Metro Atlanta Chamber,mdyer@macoc.com,,,
Nick,Fernandez,"Senior Director, Government Affairs, Public Policy",Metro Atlanta Chamber,nfernandez@macoc.com,,,
Zach,Fiore,"Director, Talent Pipeline Management",Metro Atlanta Chamber,zfiore@macoc.com,,,
Alex,Gonzalez,Chief Innovation & Marketing Officer,Metro Atlanta Chamber,agonzalez@macoc.com,,,
Marshall,Guest,Chief Strategy Officer,Metro Atlanta Chamber,mguest@macoc.com,,,
Justin,Haight,"Senior Director of Talent Partnerships, Public Policy",Metro Atlanta Chamber,jhaight@macoc.com,,,
Stefan,Harrigan,"Senior Manager, Global Business Development",Metro Atlanta Chamber,sharrigan@macoc.com,,,
Musaddaq,Hassan,"Coordinator, Infrastructure",Metro Atlanta Chamber,mhassan@macoc.com,,,
Nasan,Hayes,Facilties Coordinator,Metro Atlanta Chamber,nhayes@macoc.com,,,
Robert,Herrig,"Director, Supply Chain & Advanced Manufacturing",Metro Atlanta Chamber,rherrig@macoc.com,,,
Chauncey,Hill,Senior Project Coordinator,Metro Atlanta Chamber,chill@macoc.com,,,
Dylan,Horne,"Senior Project Manager, Economic Development",Metro Atlanta Chamber,dhorne@macoc.com,,,
Anna,Hovater,"Senior Project Coordinator, Talent Pipeline",Metro Atlanta Chamber,ahovater@macoc.com,,,
Brittany,Jenkins-Morrow,"Program Director, Connect to Work Georgia",Metro Atlanta Chamber,bmorrow@macoc.com,,,
Rebecca,Jordan,"Director, Business Recruitment, Economic Development",Metro Atlanta Chamber,rjordan@macoc.com,,,
Stephane,Leblois,Director of Technology & Innovation,Metro Atlanta Chamber,sleblois@macoc.com,,,
Katie,Kirkpatrick,President & CEO,Metro Atlanta Chamber,katiekirkpatrick@macoc.com,,,
Trucly,Knight,Talent Coordinator,Metro Atlanta Chamber,tknight@macoc.com,,,
Anna,Leach,Project Coordinator,Metro Atlanta Chamber,aleach@macoc.com,,,
Barton,Lowrey,"Vice President, Community Development",Metro Atlanta Chamber,blowrey@macoc.com,,,
Denise,Martin,"Vice President, Finance & Accounting",Metro Atlanta Chamber,denise.martin@macoc.com,,,
Jack,Murphy,Senior Account Executive,Metro Atlanta Chamber,jmurphy@macoc.com,,,
Laurin,Mcclung,Director of Communications,Metro Atlanta Chamber,lmcclung@macoc.com,,,
Angelia,O’Neal,"Talent Acquisition Coordinator, Connect to Work Georgia",Metro Atlanta Chamber,aoneal@macoc.com,,,
Sky,Park,"Director, Legal Affairs",Metro Atlanta Chamber,spark@macoc.com,,,
Debbie,Quijada,"Talent Coordinator, Georgia Intern App",Metro Atlanta Chamber,dquijada@macoc.com,,,
Mary,Rogers,Project Coordinator,Metro Atlanta Chamber,mlr1@macoc.com,,,
Jazz,Ross,Communication Specialist,Metro Atlanta Chamber,jross@macoc.com,,,
Gregg,Simon,Senior Vice President of Business Recruitment,Metro Atlanta Chamber,gsimon@macoc.com,,,
Alexis,Smith,Staff Accountant,Metro Atlanta Chamber,asmith@macoc.com,,,
Caroline,Stacey,Project Coordinator,Metro Atlanta Chamber,cms2@macoc.com,,,
Vanessa,Tallie,"Marketing, Innovation, and Entrepreneur Manager",Metro Atlanta Chamber,vtallie@macoc.com,,,
Abby,Turano,"Vice President, Strategic Communications",Metro Atlanta Chamber,aturano@macoc.com,,,
Maggie,Wigton,Government Affairs Manager,Metro Atlanta Chamber,mwigton@macoc.com,,,
Jade,Wild,Marketing Manager,Metro Atlanta Chamber,jwild@macoc.com,,,
Jared,Winston,Digital Content Manager,Metro Atlanta Chamber,jwinston@macoc.com,,,
Heather,Worthan,Marketing Director,Metro Atlanta Chamber,hworthan@macoc.com,,,
Katherine,Zitsch,Director of Water Strategy,Metro Atlanta Chamber,kzitsch@macoc.com,,,
Executive,Leadership,Sharon Mason,Cobb Chamber,smason@cobbchamber.org,,,
Amanda,Seals,"Executive Vice President, Advocacy & Government Relations",Cobb Chamber,aseals@cobbchamber.org,,,
Coleman,Loftin,"Senior Manager, Government Relations",Cobb Chamber,cloftin@cobbchamber.org,,,
Amanda,Blanton,"Senior Director, Economic Development",Cobb Chamber,ablanton@cobbchamber.org,,,
Stephanie,Cox,"Senior Director, Existing Industry",Cobb Chamber,scox@cobbchamber.org,,,
Katie,Troy,Economic Development Manager,Cobb Chamber,ktroy@cobbchamber.org,,,
Nelson,Geter,Executive Director,Cobb Chamber,ngeter@cobbchamber.org,,,
​Monica,Gonzalez,"Senior Director, Human Resources & Technology",Cobb Chamber,mgonzalez@cobbchamber.org,,,
Amy,Selby,"Executive Vice President, Marketing & Communications",Cobb Chamber,aselby@cobbchamber.org,,,
Anna,Goolsby,"Senior Director, Digital Communications",Cobb Chamber,agoolsby@cobbchamber.org,,,
​Olivia,Harris,"Senior Manager, Marketing & Communications",Cobb Chamber,oharris@cobbchamber.org,,,
Mandy,Burton,"Executive Vice President, Member Development",Cobb Chamber,mburton@cobbchamber.org,,,
Elizabeth,Colletti,"Senior Director, Member Strategy",Cobb Chamber,ecolletti@cobbchamber.org,,,
Jong,Kim,Chairman’s Circle and Premier Member Engagement Director,Cobb Chamber,jkim@cobbchamber.org,,,
Savannah,Black,"Senior Manager, Member Engagement",Cobb Chamber,sblack@cobbchamber.org,,,
Emily,Walls,"Senior Director, Member Development",Cobb Chamber,ewalls@cobbchamber.org,,,
Michele,Howard,"Executive Vice President, Programs & Leadership Development",Cobb Chamber,mhoward@cobbchamber.org,,,
Kai,Lawrence,"Senior Manager, Leadership Programs",Cobb Chamber,klawrence@cobbchamber.org,,,
Nick,Masino,President & CEO,Gwinnett Chamber,nick@gwinnettchamber.org,,,
Paul,Oh,"Vice President, Public Policy & External Affairs",Gwinnett Chamber,pauloh@gwinnettchamber.org,,,
Megan,Lesko,"Sr. Vice President, Membership",Gwinnett Chamber,mlesko@gwinnettchamber.org,,,
Tyeme,Woods,"Director, Membership Development",Gwinnett Chamber,twoods@gwinnettchamber.org,,,
Amanda,Petrone,"Sr. Manager, Membership Development",Gwinnett Chamber,apetrone@gwinnettchamber.org,,,
Margaret,Phillips,"Sr. Manager, Membership Development",Gwinnett Chamber,mphillips@gwinnettchamber.org,,,
Karen,Lanphear,Membership Services Representative,Gwinnett Chamber,klanphear@gwinnettchamber.org,,,
Ansley,Brewer,"Sr. Director, Member Services",Gwinnett Chamber,abrewer@gwinnettchamber.org,,,
Andrianna,Butler,"Manager, Member Services",Gwinnett Chamber,abutler@gwinnettchamber.org,,,
Candy,Rodriguez,"Manager, Small Business Services",Gwinnett Chamber,crodriguez@gwinnettchamber.org,,,
Alicia,Krogh,"Sr. Vice President, Executive Engagement & Programs",Gwinnett Chamber,akrogh@gwinnettchamber.org,,,
April,Perry,"Sr. Director, Programs & Events",Gwinnett Chamber,aperry@gwinnettchamber.org,,,
Maggie,Toburen,"Sr. Manager, Programs & Events",Gwinnett Chamber,mtoburen@gwinnettchamber.org,,,
Kelly,Martin,"Manager, Programs & Events",Gwinnett Chamber,kmartin@gwinnettchamber.org,,,
Lisa,Sherman,"Sr. Vice President, Marketing & Communications",Gwinnett Chamber,lsherman@gwinnettchamber.org,,,
Meredith,Bailey,Creative Director,Gwinnett Chamber,mbailey@gwinnettchamber.org,,,
Nick,Gosen,"Manager, Visual Content & Production",Gwinnett Chamber,ngosen@gwinnettchamber.org,,,
Alexys,Flores,"Coordinator, Marketing & Communications",Gwinnett Chamber,aflores@gwinnettchamber.org,,,
Dabbney,Sanchez,Marketing Coordinator,Gwinnett Chamber,dsanchez@gwinnettchamber.org,,,
Patricia,Sledge,"Sr. Vice President, Accounting & Finance",Gwinnett Chamber,psledge@gwinnettchamber.org,,,
Megan,Jones,Senior Accountant,Gwinnett Chamber,mjones@gwinnettchamber.org,,,
Patty,Razo,Accounting Manager,Gwinnett Chamber,prazo@gwinnettchamber.org,,,
Andrew,Hickey,"Sr. Director, Economic Development",Gwinnett Chamber,ahickey@partnershipgwinnett.com,,,
Rebecca,Reis,"Sr. Director, Marketing, Communications & Events",Gwinnett Chamber,rreis@partnershipgwinnett.com,,,
Amanda,Phelps,"Project Manager, Existing Industry",Gwinnett Chamber,aphelps@partnershipgwinnett.com,,,
Olivia,Gazda,"Project Manager, Economic Development",Gwinnett Chamber,ogazda@partnershipgwinnett.com,,,
Melissa,Ramirez,"Director, Gwinnett Young Professionals",Gwinnett Chamber,mramirez@gwinnettchamber.org,,,
Leana,Martinez,"Manager, Gwinnett Young Professionals",Gwinnett Chamber,lmartinez@gwinnettchamber.org,,,
Deirdra,Cox,"Executive Director, Gwinnett Chamber Foundation",Gwinnett Chamber,dcox@gwinnettchamber.org,,,
"""

def run_import():
    f = StringIO(csv_data.strip())
    reader = csv.DictReader(f)
    
    updated_count = 0

    # Structural cleanup list for malformed scraper outputs
    scrapper_placeholders = ['Senior', 'Dcorso', 'Kputnam', 'Dray', 'Jrys', 'Dwilliams', 'Jparrish', 'Gyanis', 'Kbrigman', 'Executive']

    for row in reader:
        email = row['Email'].strip().lower()
        if not email:
            continue
            
        first = row['First Name'].strip()
        last = row['Last Name'].strip()
        title = row['Title'].strip()
        org = row['Organization'].strip()
        
        # --- EXPLICIT SCRAPER CLEANUP OVERRIDES ---
        # If the Title column contains a full name (like 'Katie Kirkpatrick' or 'Dan Corso') 
        # and the first column caught placeholder garbage, correct the field map completely.
        if first in scrapper_placeholders:
            full_name_string = title # Extract actual name from where it got slipped
            name_parts = full_name_string.split()
            
            if len(name_parts) >= 2:
                first = name_parts[0]
                last = " ".join(name_parts[1:])
            else:
                first = full_name_string
                last = ""
                
            # Since the title field was storing the name, assign a default structural title
            title = "Chamber Executive"

        # Update or create database values matching on unique email strings
        lead, created = ChamberLead.objects.update_or_create(
            email=email,
            defaults={
                'first_name': first,
                'last_name': last,
                'name': f"{first} {last}".strip(),
                'title': title if title else "Chamber Executive",
                'organization': org,
                'chamber': org,
                'phone': row['Phone'].strip() or None,
                'extension': row['Extension'].strip() or None,
                'avatar_url': row['Avatar Image URL'].strip() or None,
            }
        )
        updated_count += 1

    print(f"Successfully cleaned and synchronized {updated_count} database records.")

if __name__ == '__main__':
    run_import()