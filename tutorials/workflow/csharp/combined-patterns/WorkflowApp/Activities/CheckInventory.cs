using Dapr.Client;
using Dapr.Workflow;

namespace WorkflowApp.Activities;

internal sealed class CheckInventory(DaprClient daprClient) : WorkflowActivity<OrderItem, ActivityResult>
{
    public override async Task<ActivityResult> RunAsync(WorkflowActivityContext context, OrderItem orderItem)
    {
        Console.WriteLine($"{nameof(CheckInventory)}: Received input: {orderItem}.");

        var productInventory = await daprClient.GetStateAsync<ProductInventory>(
                Constants.DAPR_INVENTORY_COMPONENT,
                orderItem.ProductId);

        if (productInventory == null)
        {
            return new ActivityResult(IsSuccess: false);
        }

        var isAvailable = productInventory.Quantity >= orderItem.Quantity;
        return new ActivityResult(IsSuccess: isAvailable);
    }
}

internal sealed record ActivityResult(bool IsSuccess, string Message = "");
