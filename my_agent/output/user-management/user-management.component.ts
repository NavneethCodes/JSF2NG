import { Component, OnInit, ViewChild } from '@angular/core';
import { UserService, User, UserRole } from './user.service'; // Assuming UserService and User model exist
import { MessageService } from 'primeng/api'; // For displaying messages
import { Dialog } from 'primeng/dialog'; // For dialog manipulation
import { Table } from 'primeng/table'; // For table manipulation

@Component({
  selector: 'app-user-management',
  templateUrl: './user-management.component.html',
  styleUrls: ['./user-management.component.css'],
  providers: [MessageService] // Provide MessageService for this component
})
export class UserManagementComponent implements OnInit {
  @ViewChild('userDialog') userDialog!: Dialog;
  @ViewChild('userTable') userTable!: Table;

  users: User[] = [];
  searchKeyword: string = '';
  selectedUser: User | null = null;
  editUser: User = { id: '', name: '', email: '', role: UserRole.USER }; // Default user for editing
  isEditMode: boolean = false;

  roles = Object.values(UserRole);

  constructor(private userService: UserService, private messageService: MessageService) { }

  ngOnInit(): void {
    this.loadUsers();
  }

  loadUsers(): void {
    this.userService.getUsers().subscribe(data => {
      this.users = data;
    });
  }

  searchUsers(): void {
    this.userService.searchUsers(this.searchKeyword).subscribe(data => {
      this.users = data;
    });
  }

  onRowSelect(event: any): void {
    this.selectedUser = event.data;
    // You might want to populate editUser here if needed, or only when Edit button is clicked
  }

  showEditDialog(user: User): void {
    this.editUser = { ...user }; // Clone user data for editing
    this.isEditMode = true;
    this.userDialog.show(); // Use ViewChild to control the dialog
  }

  showAddDialog(): void {
    this.editUser = { id: '', name: '', email: '', role: UserRole.USER }; // Reset form for new user
    this.isEditMode = false;
    this.userDialog.show();
  }

  hideDialog(): void {
    this.userDialog.hide();
  }

  saveUser(): void {
    if (this.isEditMode) {
      this.userService.updateUser(this.editUser).subscribe({
        next: () => {
          this.messageService.add({ severity: 'success', summary: 'Success', detail: 'User updated successfully' });
          this.loadUsers(); // Refresh user list
          this.hideDialog();
        },
        error: (err) => {
          this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to update user' });
          console.error(err);
        }
      });
    } else {
      this.userService.createUser(this.editUser).subscribe({
        next: () => {
          this.messageService.add({ severity: 'success', summary: 'Success', detail: 'User created successfully' });
          this.loadUsers(); // Refresh user list
          this.hideDialog();
        },
        error: (err) => {
          this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to create user' });
          console.error(err);
        }
      });
    }
  }

  deleteUser(user: User): void {
    if (confirm('Are you sure you want to delete ' + user.name + '?')) {
      this.userService.deleteUser(user.id).subscribe({
        next: () => {
          this.messageService.add({ severity: 'success', summary: 'Success', detail: 'User deleted successfully' });
          this.users = this.users.filter(u => u.id !== user.id); // Remove from current list
          if (this.selectedUser && this.selectedUser.id === user.id) {
            this.selectedUser = null;
          }
        },
        error: (err) => {
          this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to delete user' });
          console.error(err);
        }
      });
    }
  }
}
