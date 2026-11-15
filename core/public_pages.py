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
