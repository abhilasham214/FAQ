"""Generate a synthetic, seeded dataset of resolved support tickets.

Usage: python backend/scripts/generate_sample_data.py [output.csv]
All content is invented; no real customer data is involved.
"""
from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

SEED = 7
TICKETS_PER_THEME = 17

# theme -> [(title, description, resolution)]: each issue has its own matching fix
THEMES = {
    "payment_failed": [
        ("Card payment declined at checkout", "Customer's card was declined at checkout even though the card is valid and has funds.",
         "Issuer had blocked the transaction for risk reasons; customer contacted the bank and retried successfully."),
        ("Payment failed with generic error", "Checkout shows 'Payment failed, please try again' and no charge is created.",
         "Gateway credentials for the merchant had expired; rotated the credentials and retried the payment."),
        ("3-D Secure step fails", "The 3-D Secure verification page closes or times out and the payment is marked failed.",
         "The 3-D Secure redirect URL was misconfigured; corrected the return URL and payments went through."),
        ("Payment gateway returned error code", "Gateway returned an error response during authorization and the order was not completed.",
         "Payment retried through the backup gateway route after the primary gateway timed out."),
        ("UPI payment failed after approval", "Customer approved the UPI request but the order shows payment failed.",
         "UPI collect request had expired before confirmation; customer initiated a fresh payment and it succeeded."),
        ("Wallet payment rejected", "Wallet payment is rejected at the final step with no clear message.",
         "Wallet balance was below the order total; customer topped up the wallet and completed the payment."),
    ],
    "payment_pending": [
        ("Payment stuck in pending state", "Customer payment remains pending after successful authorization.",
         "Reconciled the transaction with the gateway report and updated the payment state to completed."),
        ("Order shows pending but money debited", "Amount was debited from the customer's account but the order still shows payment pending.",
         "Confirmed the debit with the bank, then manually marked the payment as paid and released the order."),
        ("Pending payment not updating", "Payment has been in pending for over 24 hours with no status change.",
         "Ran the reconciliation job for the affected window; pending payments were settled automatically."),
        ("Transaction pending after bank confirmation", "Bank confirmed the debit but our system never moved the payment out of pending.",
         "Fetched the final status from the gateway status API and updated the payment record accordingly."),
        ("Subscription renewal pending", "Renewal payment remains pending and the subscription is not extended.",
         "Reconciled the renewal payment and extended the subscription period once the payment was confirmed."),
        ("Pending status after webhook delay", "Payment status was not updated because the gateway webhook arrived late or not at all.",
         "Missed webhook was replayed manually, which moved the payment from pending to success."),
    ],
    "authentication": [
        ("Cannot log in after password reset", "User resets the password but login still says invalid credentials.",
         "Cleared the user's stale sessions and tokens server-side; user logged in with the new password."),
        ("Session expires immediately after login", "User is logged out within seconds and redirected to the login page.",
         "Session cookie was being rejected because of a domain mismatch; corrected the cookie domain setting."),
        ("Reset password link expired", "Password reset email link shows expired even when opened right away.",
         "Reset token lifetime was too short due to a config error; increased it and reissued the link."),
        ("Two-factor code not accepted", "The one-time code from the authenticator app is rejected as invalid.",
         "Device clock was out of sync so codes were rejected; synced the time and the code was accepted."),
        ("SSO login loops back to sign-in", "After signing in through SSO, the user is redirected back to the login page repeatedly.",
         "Fixed the SSO callback URL mapping and the login redirect loop stopped."),
        ("Account locked after failed attempts", "User account is locked and the unlock email never arrives.",
         "Unlocked the account manually and resent the unlock email after correcting the user's email address."),
    ],
    "refund": [
        ("Refund not received", "Customer cancelled the order two weeks ago and still has not received the refund.",
         "Refund had been submitted to the bank; provided the ARN so the customer could track it, funds arrived in 5-7 business days."),
        ("Refund shows processed but no money", "The order shows refund processed but the amount is not in the customer's account.",
         "Shared the bank reference number with the customer; the bank credited the amount after its settlement cycle."),
        ("Partial refund amount incorrect", "Refund was issued for less than the amount the customer was charged.",
         "Corrected the refund amount to include the shipping fee and issued the remaining balance."),
        ("Refund stuck in initiated status", "Refund has been in initiated status for several days.",
         "Re-triggered the stuck refund through the gateway dashboard and confirmed the status changed to processed."),
        ("Refund to wrong payment method", "Refund was sent to a wallet instead of the original card.",
         "Refund routed to the original payment source after the wallet credit was reversed."),
        ("Refund failed at gateway", "Refund request was rejected by the gateway with a failure status.",
         "Gateway rejected the refund because the original transaction was past the refund window; issued a manual bank transfer instead."),
    ],
    "notification_failure": [
        ("Confirmation emails not delivered", "Customers are not receiving order confirmation emails.",
         "SPF and DKIM records were missing for the sending domain; added them and delivery recovered."),
        ("SMS OTP not received", "Users do not receive the SMS one-time password during signup.",
         "SMS provider had throttled the sender ID; switched to the approved sender and OTPs were delivered."),
        ("Push notifications not appearing", "Mobile push notifications are not showing up for some users.",
         "Device token had expired; the app re-registered the push token after an update."),
        ("Emails landing in spam", "Transactional emails are being delivered to the spam folder.",
         "Moved transactional emails to a dedicated sending domain with proper authentication, which improved inbox placement."),
        ("Duplicate notification sent", "Customer received the same alert three times.",
         "Notification worker retried the job after a timeout; added a de-duplication key so each alert is sent once."),
        ("Notification delayed by hours", "Shipping update notifications arrive many hours late.",
         "Notification queue worker had stalled; restarted the worker and the backlog was processed."),
    ],
    "data_sync": [
        ("Inventory counts out of sync", "Inventory numbers in the dashboard do not match the warehouse system.",
         "Cleared the sync cursor and triggered a full resync, after which the records matched."),
        ("Customer records not syncing to CRM", "New customer records are missing in the CRM after signup.",
         "Sync job hit a schema mismatch after a field rename; updated the mapping and re-ran the full sync."),
        ("Data sync job failing overnight", "The nightly synchronization job fails partway through.",
         "Increased the job timeout since the batch exceeded the limit; the nightly sync now completes."),
        ("Changes not reflected across devices", "Profile changes made on the web app do not appear on mobile.",
         "Mobile app was serving a cached profile; forced a cache refresh and shortened the cache expiry."),
        ("Stale data shown on reports", "Reports display last week's numbers instead of current data.",
         "Invalidated the stale cache layer so reports read fresh data from the source."),
        ("Sync conflict overwrote records", "Two systems updated the same record and one update was lost.",
         "Restored the overwritten record from backup and enabled last-modified checks to prevent conflicting overwrites."),
    ],
    "api_failure": [
        ("API returns 500 error", "Calls to the orders endpoint return HTTP 500 intermittently.",
         "A null-pointer bug in the orders handler was patched and deployed; the 500 errors stopped."),
        ("API requests timing out", "Partner integration requests time out after 30 seconds.",
         "Added a missing database index behind the slow query; response times dropped below the timeout."),
        ("401 Unauthorized with valid API key", "Client receives 401 responses even though the API key is valid.",
         "API key was scoped to the sandbox environment; issued a production key and requests succeeded."),
        ("Rate limit errors on API", "Integration is receiving 429 Too Many Requests during normal usage.",
         "Raised the rate limit for the partner's key and advised exponential backoff on retries."),
        ("Webhook delivery failing", "Our webhook endpoint calls fail with 502 from the gateway.",
         "Upstream service was restarting during deploys; enabled webhook retries so deliveries succeed after the restart."),
        ("API response missing fields", "The API response no longer contains the expected fields after the release.",
         "Restored the removed fields in the response and released a hotfix for backward compatibility."),
    ],
    "duplicate_transaction": [
        ("Customer charged twice for one order", "Customer was charged twice for the same order.",
         "Identified the duplicate charge via the idempotency key logs and refunded the extra transaction."),
        ("Duplicate transactions after retry", "A retry after a timeout created two separate transactions.",
         "Enabled idempotency keys on payment creation so retries no longer create duplicates."),
        ("Double debit on subscription", "Subscription was billed twice in the same billing cycle.",
         "Merged the duplicate payment records and issued a credit for the extra billing cycle."),
        ("Two orders created from one click", "Double-clicking the pay button created two orders and two charges.",
         "Cancelled the duplicate order and refunded the second charge; disabled the pay button after the first click."),
        ("Duplicate payment after page refresh", "Refreshing the payment page created a second payment.",
         "Refunded the second payment and changed the payment page to reuse the existing order on refresh."),
        ("Same invoice paid twice", "The same invoice shows two successful payments.",
         "Applied the second payment as account credit against the next invoice at the customer's request."),
    ],
    "configuration": [
        ("Feature not visible after enabling", "Feature flag was enabled but users cannot see the new feature.",
         "Feature flag was scoped to a different tenant; updated the scope and cleared the config cache."),
        ("Incorrect tax applied at checkout", "Tax rate at checkout does not match the configured region.",
         "Corrected the region tax table in the account configuration and recalculated open carts."),
        ("Wrong currency displayed", "Prices are displayed in USD instead of the store's local currency.",
         "Updated the store currency setting and refreshed the price cache."),
        ("Custom domain not working", "Custom domain shows a certificate error after setup.",
         "DNS CNAME was pointing to the wrong target; corrected the record and reissued the certificate."),
        ("Role permissions not applied", "A user assigned the admin role cannot access the settings page.",
         "Permission changes had not propagated; the user signed out and back in, and the role was applied."),
        ("Environment settings mismatch", "Staging behaves differently from production because of different settings.",
         "Compared both environments and aligned the differing settings so staging matches production."),
    ],
}

CONTEXT = [
    "Reported via chat.", "Reported via email.", "Escalated from tier 1.", "Affects a single customer.",
    "Seen by multiple customers this week.", "Raised by an enterprise account.", "Occurred on mobile app.",
    "Occurred on the web app.", "Started after the latest release.", "First noticed on Monday.",
]
FOLLOW_UP = [
    "Customer confirmed the issue is resolved.", "Verified fix in production.",
    "Monitored for 48 hours with no recurrence.", "Documented in the runbook.", "Closed after customer confirmation.",
]


def generate() -> list[dict]:
    rng = random.Random(SEED)
    rows: list[dict] = []
    for issues in THEMES.values():
        for _ in range(TICKETS_PER_THEME):
            title, description, resolution = rng.choice(issues)
            rows.append(
                {
                    "title": title,
                    "description": f"{description} {rng.choice(CONTEXT)}",
                    "resolution": f"{resolution} {rng.choice(FOLLOW_UP)}",
                    "status": "resolved",
                }
            )
    rng.shuffle(rows)
    for i, row in enumerate(rows, start=1):
        row["ticket_id"] = f"T{i:03d}"
    return rows


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "data" / "sample_tickets.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = generate()
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ticket_id", "title", "description", "resolution", "status"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} tickets to {out}")


if __name__ == "__main__":
    main()
