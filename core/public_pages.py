"""
core/public_pages.py

Public, no-login pages the app stores link to.
  /account-deletion/ — how to delete an account (required by Google Play).
"""

from django.conf import settings
from django.http import HttpResponse
from django.utils.html import escape

ACCOUNT_DELETION_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Delete your account – A Muslim Matchmaker</title>
<style>
 body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;max-width:720px;margin:0 auto;padding:24px 16px;color:#1e293b;line-height:1.6;background:#fff}}
 h1{{font-size:1.6rem}} h2{{font-size:1.15rem;margin-top:1.8em}} li{{margin:.3em 0}}
 .box{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px}}
 a{{color:#6366f1}}
</style></head><body>
<h1>Delete your A Muslim Matchmaker account</h1>
<p>A Muslim Matchmaker is operated by FAITHFUL FOUNDATIONS LIMITED. You can delete your account and its associated data at any time.</p>

<h2>Option 1: Delete in the app</h2>
<div class="box"><ol>
 <li>Open the <strong>A Muslim Matchmaker</strong> app and sign in.</li>
 <li>Go to <strong>Settings → Security → Delete Account</strong>.</li>
 <li>Choose a reason, add any feedback, and confirm.</li>
</ol>
<p>Your account is closed immediately and your profile is no longer shown to other users.</p></div>

<h2>Option 2: Ask us by email</h2>
<p>If you can no longer sign in, email <a href="mailto:{email}?subject=Account%20deletion%20request">{email}</a> from the email address registered to your account, with the subject “Account deletion request”. We will confirm and complete the deletion within 30 days.</p>

<h2>What is deleted</h2>
<ul>
 <li>Your profile, photographs and profile answers (including religious and any health information you provided)</li>
 <li>Your Wali details, preferences, saved profiles and match requests</li>
 <li>Your chat messages and profile-view history</li>
</ul>

<h2>What may be kept, and for how long</h2>
<p>As described in section 14.4 of our <a href="https://amuslimmatchmaker.com/privacy-policy/">Privacy Policy</a>, we may keep limited records where the law or a legitimate purpose requires it: transaction and subscription records, consent records, complaints, safeguarding and fraud-prevention information, banned-user controls and information needed for legal claims. These are kept only as long as needed for that purpose (for example, accounting records for the statutory period). Data in backups is removed through the normal backup cycle.</p>

<h2>Subscriptions</h2>
<p>Deleting your account does not cancel a subscription bought through the App Store or Google Play. Please cancel it in your Apple ID or Google Play subscription settings to avoid further charges.</p>
</body></html>"""


def account_deletion(request):
    email = escape(getattr(settings, "SUPPORT_EMAIL", "info@amuslimmatchmaker.com"))
    return HttpResponse(ACCOUNT_DELETION_HTML.format(email=email))


CHILD_SAFETY_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Child safety standards – A Muslim Matchmaker</title>
<style>
 body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;max-width:720px;margin:0 auto;padding:24px 16px;color:#1e293b;line-height:1.6;background:#fff}}
 h1{{font-size:1.6rem}} h2{{font-size:1.15rem;margin-top:1.8em}} li{{margin:.3em 0}} a{{color:#6366f1}}
</style></head><body>
<h1>Child safety standards</h1>
<p>A Muslim Matchmaker is operated by FAITHFUL FOUNDATIONS LIMITED. We have zero tolerance for child sexual abuse and exploitation (CSAE), including child sexual abuse material (CSAM), grooming and any sexualisation of minors.</p>

<h2>Adults only</h2>
<ul>
 <li>The app is a marriage-focused service for adults aged 18 and over. Users must confirm their date of birth when registering.</li>
 <li>Accounts we believe belong to a person under 18 are suspended and removed.</li>
</ul>

<h2>What is prohibited</h2>
<ul>
 <li>Any content, message or image that sexualises, exploits or endangers a child.</li>
 <li>Attempts to contact, groom or arrange to meet a minor.</li>
 <li>Sharing, requesting or linking to CSAM in any form.</li>
</ul>

<h2>How to report</h2>
<ul>
 <li><strong>In the app:</strong> open the profile and use <strong>Report</strong>. Reports go directly to our moderation team. You can also block the user.</li>
 <li><strong>By email:</strong> <a href="mailto:{email}?subject=Child%20safety%20report">{email}</a> (subject “Child safety report”).</li>
</ul>

<h2>How we respond</h2>
<ul>
 <li>Child safety reports are prioritised and reviewed by our team.</li>
 <li>Offending content and accounts are removed and the user is banned from the service.</li>
 <li>We report apparent CSAM and child exploitation to the relevant authorities, including the UK National Crime Agency (CEOP) and the National Center for Missing &amp; Exploited Children (NCMEC), and we preserve information as required by law.</li>
 <li>We comply with all applicable child safety laws and cooperate with law enforcement.</li>
</ul>

<h2>Child safety contact</h2>
<p>Our designated contact for child safety and CSAM prevention is <a href="mailto:{email}">{email}</a>.</p>
</body></html>"""


def child_safety(request):
    email = escape(getattr(settings, "SUPPORT_EMAIL", "info@amuslimmatchmaker.com"))
    return HttpResponse(CHILD_SAFETY_HTML.format(email=email))
