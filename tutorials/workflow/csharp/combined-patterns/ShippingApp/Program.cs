using Dapr;
using Dapr.Client;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDaprClient();
var app = builder.Build();
app.UseCloudEvents();

/// This endpoint is called by the CheckShippingDestination activity in the WorkflowApp.
app.MapPost("/checkDestination", (
    Order order) =>
{
    Console.WriteLine($"checkDestination: Received input: {order}.");
    var result = new ShippingDestinationResult(IsSuccess: true);
    return Results.Ok(result);
});

// This endpoint handles messages that are published to the shipment-registration-events topic.
// The RegisterShipment activity in the WorkflowApp is publishing to this topic.
// This method is publishing a message to the shipment-registration-confirmed-events topic.
app.MapPost("/registerShipment", async (
    Order order,
    DaprClient daprClient) =>
{
    Console.WriteLine($"registerShipment: Received input: {order}.");
    var status = new ShipmentRegistrationStatus(OrderId: order.Id, IsSuccess: true);

    if (order.Id == string.Empty)
    {
        Console.WriteLine($"Order Id is empty!");
    }
    else
    {
        await daprClient.PublishEventAsync(
            Constants.DAPR_PUBSUB_COMPONENT,
            Constants.DAPR_PUBSUB_CONFIRMED_TOPIC,
            status);
    }

    return Results.Created();
});

app.Run();

internal sealed record Order(string Id, OrderItem OrderItem, CustomerInfo CustomerInfo);
internal sealed record OrderItem(string ProductId, string ProductName, int Quantity, decimal TotalPrice);
internal sealed record CustomerInfo(string Id, string Country);
internal sealed record ShipmentRegistrationStatus(string OrderId, bool IsSuccess, string Message = "");
internal sealed record ShippingDestinationResult(bool IsSuccess, string Message = "");