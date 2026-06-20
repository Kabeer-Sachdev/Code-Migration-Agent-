using Microsoft.Extensions.DependencyInjection;

class Program
{
    static void Main(string[] args)
    {
        var services = new ServiceCollection();
        services.AddScoped<UserService>();
        services.AddScoped<OrderService>();

        var provider = services.BuildServiceProvider();
        var userService = provider.GetRequiredService<UserService>();
        var orderService = provider.GetRequiredService<OrderService>();

        // Add users
        userService.AddUser("John Doe", "john@example.com");
        userService.AddUser("Jane Smith", "jane@example.com");
        userService.AddUser("Bob Johnson", "bob@example.com");

        // Get user
        var user = userService.GetUser("john@example.com");
        Console.WriteLine($"Found User: {user?.Name} ({user?.Email})");

        // Get all users
        var allUsers = userService.GetAllUsers();
        Console.WriteLine($"\nTotal Users: {allUsers.Count}");
        foreach (var u in allUsers)
        {
            Console.WriteLine($"  - {u.Name} ({u.Email})");
        }

        // Update user
        userService.UpdateUser("jane@example.com", "Jane Doe-Smith");
        Console.WriteLine($"\nUpdated Jane's name");

        // Create orders
        orderService.CreateOrder("john@example.com", new List<string> { "Item1", "Item2" });
        orderService.CreateOrder("jane@example.com", new List<string> { "Item3" });

        Console.WriteLine($"\nOrders created successfully!");
    }
}
