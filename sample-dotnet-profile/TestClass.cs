using System;
using System.Collections.Generic;
using System.Linq;

public class UserService
{
    private List<User> users = new List<User>();
    
    public void AddUser(string name, string email)
    {
        if (string.IsNullOrEmpty(name) || string.IsNullOrEmpty(email))
            throw new ArgumentException("Name and email are required");
            
        var user = new User { Name = name, Email = email, CreatedAt = DateTime.UtcNow };
        users.Add(user);
    }
    
    public User GetUser(string email)
    {
        return users.FirstOrDefault(u => u.Email == email);
    }
    
    public List<User> GetAllUsers()
    {
        return users;
    }
    
    public bool DeleteUser(string email)
    {
        var user = GetUser(email);
        if (user != null)
        {
            users.Remove(user);
            return true;
        }
        return false;
    }
    
    public void UpdateUser(string email, string newName)
    {
        var user = GetUser(email);
        if (user != null)
        {
            user.Name = newName;
            user.UpdatedAt = DateTime.UtcNow;
        }
    }
}

public class User
{
    public string Name { get; set; }
    public string Email { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }
}

public class OrderService
{
    private List<Order> orders = new List<Order>();
    
    public void CreateOrder(string userId, List<string> items)
    {
        var order = new Order 
        { 
            UserId = userId, 
            Items = items,
            Status = "PENDING",
            CreatedAt = DateTime.UtcNow
        };
        orders.Add(order);
    }
    
    public Order GetOrder(string orderId)
    {
        return orders.FirstOrDefault(o => o.Id == orderId);
    }
}

public class Order
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string UserId { get; set; }
    public List<string> Items { get; set; }
    public string Status { get; set; }
    public DateTime CreatedAt { get; set; }
}
