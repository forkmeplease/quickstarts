# Dapr state management (HTTP Client)

In this quickstart, you'll create a microservice to demonstrate Dapr's state management API. The service generates messages to store in a state store. See [Why state management](https://docs.dapr.io/developing-applications/building-blocks/state-management/) to understand when to use this API.

Visit [this](https://docs.dapr.io/developing-applications/building-blocks/state-management/) link for more information about Dapr and State Management.

> **Note:** This example leverages HTTP `requests` only.  If you are looking for the example using the Dapr Client SDK (recommended) [click here](../sdk/).

This quickstart includes one service: Go client service `order-processor`

## Run all apps with multi-app run template file

This section shows how to run applications at once using [multi-app run template files](https://docs.dapr.io/developing-applications/local-development/multi-app-dapr-run/multi-app-overview/) with `dapr run -f .`.  This enables to you test the interactions between multiple applications.

Open a new terminal window and run  `order-processor` using the multi app run template defined in [dapr.yaml](./dapr.yaml):

1. Run the Go service app with Dapr:

<!-- STEP
name: Run order-processor service
expected_stdout_lines:
  - '== APP - order-processor == Retrieved Order: "{\"orderId\":1}"'
  - '== APP - order-processor == Retrieved Order: "{\"orderId\":2}"'
  - "Exited App successfully"
expected_stderr_lines:
output_match_mode: substring
match_order: none
background: false
sleep: 15
-->

```bash
  dapr run -f .
```

<!-- END_STEP -->

2. Stop and cleanup application process
<!-- STEP
name: Stop multi-app run 
sleep: 5
-->

```bash
dapr stop -f .
```
<!-- END_STEP -->

## Run a single app at a time with Dapr (Optional)

An alternative to running all or multiple applications at once is to run single apps one-at-a-time using multiple `dapr run .. -- go run` commands.  This next section covers how to do this.

1. Run the Go service app with Dapr:

<!-- STEP
name: Run order-processor service
expected_stdout_lines:
  - '== APP == Retrieved Order: "{\"orderId\":1}"'
  - '== APP == Retrieved Order: "{\"orderId\":2}"'
  - "Exited App successfully"
expected_stderr_lines:
output_match_mode: substring
match_order: none
background: true
sleep: 15
-->

```bash
cd ./order-processor
dapr run --app-id order-processor --resources-path ../../../resources/ -- go run .
```

The Terminal console output should look similar to this:

```text
You're up and running! Both Dapr and your app logs will appear here.

== APP == Saved Order: {"orderId":1}
== APP == Retrieved Order: "{\"orderId\":1}"
== APP == 2023/09/24 23:31:27 Deleted Order: {"orderId":1}
== APP == Saved Order: {"orderId":2}
== APP == Retrieved Order: "{\"orderId\":2}"
== APP == 2023/09/24 23:31:27 Deleted Order: {"orderId":2}
== APP == Saved Order: {"orderId":3}
== APP == Retrieved Order: "{\"orderId\":3}"
== APP == 2023/09/24 23:31:27 Deleted Order: {"orderId":3}
```

2. Stop and clean up application processes
dapr stop --app-id order-processor

<!-- END_STEP -->
