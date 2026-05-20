# AR Worker (port 8011)

Consumes `accounts_queue` for `ar_invoice`, `ar_payment_advice`, `ar_credit_note`, and `ar_soa_request`.

- Health: `GET /health`
- Manual: `POST /process-once`

See `platform_dox/17_Worker_Specifications.md` §4.
