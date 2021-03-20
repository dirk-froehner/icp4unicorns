# icp4unicorns
Integration and conversation patterns for unicorns in the passenger transport business

In this repo, I experiment with sample implementations. Some of that may eventually make it into official AWS hands-on workshop labs, quick starts, or solutions - or maybe not. Everything in this repo is to be considered as one of my private pet projects.

## Sample requests

### Sample requests for the "submit ride completion" use case:

    cd submit-ride-completion/unicorn-management-service
    curl -i https://<your-api-gw-base-url>/api/user/submit-ride-completion -d @events/standard-ride.json
    curl -i https://<your-api-gw-base-url>/api/user/submit-ride-completion -d @events/extraordinary-ride.json

### Sample requests for the "instant ride RFQ" use case:

    cd instant-ride-rfq/ride-booking-service
    curl -i https://<your-api-gw-base-url>/api/user/submit-rfq -d @events/instant-ride-rfq.json
