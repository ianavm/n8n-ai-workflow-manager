"""
Create test leads in Airtable to demonstrate the workflow.

Usage:
    python tools/create_test_leads.py
"""

import sys
import os
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config

# Load .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


# Test lead data - realistic Fourways businesses
TEST_LEADS = [
    {
        'Business Name': 'Fourways Properties & Estates',
        'Email': 'info@fourwaysproperties.co.za',
        'Phone': '+27 11 465 8900',
        'Website': 'https://fourwaysproperties.co.za',
        'Address': '123 William Nicol Drive, Fourways, Johannesburg',
        'Industry': 'real estate',
        'Location': 'Fourways, Johannesburg',
        'Rating': 4.5,
        'Social - LinkedIn': 'https://linkedin.com/company/fourways-properties',
        'Social - Facebook': 'https://facebook.com/fourwaysproperties',
        'Social - Instagram': 'https://instagram.com/fourwaysproperties',
        'Lead Score': 95,
        'Automation Fit': 'high',
        'Status': 'Todo',
        'Source': 'Google Maps Scraper',
        'Notes': 'High-fit for CRM automation - follow-up sequences, lead nurturing'
    },
    {
        'Business Name': 'Baxter & Associates Law Firm',
        'Email': 'contact@baxterlaw.co.za',
        'Phone': '+27 11 462 7300',
        'Website': 'https://baxterlaw.co.za',
        'Address': '45 Cedar Road, Fourways, Johannesburg',
        'Industry': 'legal',
        'Location': 'Fourways, Johannesburg',
        'Rating': 4.8,
        'Social - LinkedIn': 'https://linkedin.com/company/baxter-law',
        'Lead Score': 92,
        'Automation Fit': 'high',
        'Status': 'In progress',
        'Source': 'Google Maps Scraper',
        'Notes': 'Client intake automation opportunity - save 15h/week'
    },
    {
        'Business Name': 'Smile Dental Clinic Fourways',
        'Email': 'bookings@smiledental.co.za',
        'Phone': '+27 11 465 1200',
        'Website': 'https://smiledental.co.za',
        'Address': '78 Main Road, Fourways, Johannesburg',
        'Industry': 'dental',
        'Location': 'Fourways, Johannesburg',
        'Rating': 4.7,
        'Social - Facebook': 'https://facebook.com/smiledental',
        'Social - Instagram': 'https://instagram.com/smiledental',
        'Lead Score': 88,
        'Automation Fit': 'high',
        'Status': 'Todo',
        'Source': 'Google Maps Scraper',
        'Notes': 'Appointment reminders + booking automation'
    },
    {
        'Business Name': 'La Piazza Italian Restaurant',
        'Email': 'reservations@lapiazza.co.za',
        'Phone': '+27 11 467 9800',
        'Website': 'https://lapiazza.co.za',
        'Address': '22 Witkoppen Road, Fourways, Johannesburg',
        'Industry': 'restaurant',
        'Location': 'Fourways, Johannesburg',
        'Rating': 4.6,
        'Social - Instagram': 'https://instagram.com/lapiazzafourways',
        'Social - Facebook': 'https://facebook.com/lapiazza',
        'Lead Score': 85,
        'Automation Fit': 'high',
        'Status': 'Done',
        'Source': 'Google Maps Scraper',
        'Notes': 'Reservation automation + waitlist management'
    },
    {
        'Business Name': 'Summit Consulting Group',
        'Email': 'info@summitconsulting.co.za',
        'Phone': '+27 11 463 2100',
        'Website': 'https://summitconsulting.co.za',
        'Address': '156 William Nicol Drive, Fourways, Johannesburg',
        'Industry': 'consulting',
        'Location': 'Fourways, Johannesburg',
        'Rating': 4.9,
        'Social - LinkedIn': 'https://linkedin.com/company/summit-consulting',
        'Lead Score': 90,
        'Automation Fit': 'high',
        'Status': 'In progress',
        'Source': 'Google Maps Scraper',
        'Notes': 'Pipeline automation - 40% more leads possible'
    },
    {
        'Business Name': 'Fourways Plumbing Services',
        'Email': 'bookings@fourwaysplumbing.co.za',
        'Phone': '+27 82 555 6789',
        'Website': 'https://fourwaysplumbing.co.za',
        'Address': '89 Witkoppen Road, Fourways, Johannesburg',
        'Industry': 'plumbing',
        'Location': 'Fourways, Johannesburg',
        'Rating': 4.3,
        'Lead Score': 72,
        'Automation Fit': 'medium',
        'Status': 'Todo',
        'Source': 'Google Maps Scraper',
        'Notes': 'Quote automation + job scheduling'
    },
    {
        'Business Name': 'Cedar Pharmacy',
        'Email': 'info@cedarpharmacy.co.za',
        'Phone': '+27 11 465 3400',
        'Website': 'https://cedarpharmacy.co.za',
        'Address': '12 Cedar Avenue, Fourways, Johannesburg',
        'Industry': 'pharmacy',
        'Location': 'Fourways, Johannesburg',
        'Rating': 4.4,
        'Social - Facebook': 'https://facebook.com/cedarpharmacy',
        'Lead Score': 78,
        'Automation Fit': 'high',
        'Status': 'In progress',
        'Source': 'Google Maps Scraper',
        'Notes': 'Prescription reminders + loyalty program automation'
    },
    {
        'Business Name': 'Fourways Fashion Boutique',
        'Email': 'hello@fourwaysfashion.co.za',
        'Phone': '+27 11 467 8500',
        'Website': 'https://fourwaysfashion.co.za',
        'Address': '45 Witkoppen Road, Fourways, Johannesburg',
        'Industry': 'retail',
        'Location': 'Fourways, Johannesburg',
        'Rating': 4.2,
        'Social - Instagram': 'https://instagram.com/fourwaysfashion',
        'Lead Score': 80,
        'Automation Fit': 'high',
        'Status': 'In progress',
        'Source': 'Google Maps Scraper',
        'Notes': 'Customer engagement + loyalty automation'
    },
    {
        'Business Name': 'FitZone Gym Fourways',
        'Email': 'join@fitzonefw.co.za',
        'Phone': '+27 11 462 9100',
        'Website': 'https://fitzonefw.co.za',
        'Address': '88 William Nicol Drive, Fourways, Johannesburg',
        'Industry': 'fitness',
        'Location': 'Fourways, Johannesburg',
        'Rating': 4.5,
        'Social - Instagram': 'https://instagram.com/fitzonefw',
        'Social - Facebook': 'https://facebook.com/fitzonefourways',
        'Lead Score': 83,
        'Automation Fit': 'high',
        'Status': 'Todo',
        'Source': 'Google Maps Scraper',
        'Notes': 'Member engagement + class booking automation'
    },
    {
        'Business Name': 'Green Gardens Landscaping',
        'Email': 'quotes@greengardens.co.za',
        'Phone': '+27 83 444 5678',
        'Website': 'https://greengardens.co.za',
        'Address': '34 Main Road, Fourways, Johannesburg',
        'Industry': 'landscaping',
        'Location': 'Fourways, Johannesburg',
        'Rating': 4.1,
        'Lead Score': 68,
        'Automation Fit': 'medium',
        'Status': 'Todo',
        'Source': 'Google Maps Scraper',
        'Notes': 'Quote generation + job scheduling automation'
    }
]


def main():
    print("=" * 60)
    print("CREATING TEST LEADS IN AIRTABLE")
    print("=" * 60)
    print()

    config = load_config()

    # Get Airtable token from environment
    airtable_token = os.getenv('AIRTABLE_API_TOKEN')
    if not airtable_token:
        print("ERROR: AIRTABLE_API_TOKEN not found in environment")
        print("Please add it to your .env file")
        sys.exit(1)

    base_id = 'app2ALQUP7CKEkHOz'
    table_id = 'tblOsuh298hB9WWrA'

    print(f"Target Base: {base_id}")
    print(f"Target Table: {table_id}")
    print(f"Records to create: {len(TEST_LEADS)}")
    print()

    # Create Airtable client
    client = httpx.Client(
        base_url=f'https://api.airtable.com/v0/{base_id}',
        headers={
            'Authorization': f'Bearer {airtable_token}',
            'Content-Type': 'application/json'
        },
        timeout=30
    )

    # Add dates to test leads
    base_date = datetime.now()
    for i, lead in enumerate(TEST_LEADS):
        # Vary dates slightly
        scrape_date = (base_date - timedelta(days=i)).strftime('%Y-%m-%d')
        lead['Date Scraped'] = scrape_date

        # Add email sent date for leads with "Email Sent" status
        if lead['Status'] in ['Email Sent', 'Followed Up', 'Responded']:
            email_date = (base_date - timedelta(days=i-1)).strftime('%Y-%m-%d')
            lead['Email Sent Date'] = email_date

    # Create records
    created = 0
    failed = 0

    print("Creating records...")
    print()

    for i, lead in enumerate(TEST_LEADS, 1):
        try:
            payload = {'fields': lead}
            resp = client.post(f'/{table_id}', json=payload)

            if resp.status_code == 200:
                created += 1
                print(f"  + {i:2d}. {lead['Business Name']:<40} (Score: {lead['Lead Score']}, Fit: {lead['Automation Fit']})")
            else:
                failed += 1
                print(f"  - {i:2d}. {lead['Business Name']:<40} - ERROR: {resp.status_code}")
                if resp.status_code == 422:
                    print(f"       Response: {resp.text[:200]}")
        except Exception as e:
            failed += 1
            print(f"  - {i:2d}. {lead['Business Name']:<40} - EXCEPTION: {str(e)[:100]}")

    client.close()

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"+ Created: {created}")
    print(f"- Failed:  {failed}")
    print()

    if created > 0:
        print("SUCCESS! Test leads created in your Airtable base.")
        print()
        print("View them here:")
        print(f"  https://airtable.com/{base_id}")
        print()
        print("Data breakdown:")
        print(f"  • High automation fit: 7 businesses")
        print(f"  • Medium automation fit: 3 businesses")
        print(f"  • Average lead score: {sum(l['Lead Score'] for l in TEST_LEADS) // len(TEST_LEADS)}")
        print(f"  • Status distribution:")
        print(f"    - Todo: 5")
        print(f"    - In progress: 4")
        print(f"    - Done: 1")
        print()
        print("Next steps:")
        print("  1. Sort by 'Lead Score' (descending) to see highest-priority leads")
        print("  2. Filter by 'Automation Fit' = 'high' to see best opportunities")
        print("  3. Review the 'Notes' field for automation suggestions")


if __name__ == "__main__":
    main()
