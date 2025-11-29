package com.example.beans;

import javax.faces.bean.ManagedBean;
import javax.faces.bean.SessionScoped;
import java.util.ArrayList;
import java.util.List;
import com.example.model.User;

@ManagedBean(name = "userBean")
@SessionScoped
public class UserBean {
    private User currentUser = new User();
    private List<User> users = new ArrayList<>();

    public void saveUser() {
        System.out.println("Saving user: " + currentUser.getUsername());
        users.add(currentUser);
        currentUser = new User(); // Reset
    }

    public void deleteUser(User user) {
        users.remove(user);
    }

    public List<User> getUsers() { return users; }
    public void setUsers(List<User> users) { this.users = users; }
    public User getCurrentUser() { return currentUser; }
    public void setCurrentUser(User currentUser) { this.currentUser = currentUser; }
}
