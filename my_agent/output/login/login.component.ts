import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../auth.service'; // Assuming AuthService handles authentication

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css']
})
export class LoginComponent implements OnInit {
  username = '';
  password = '';
  messages: any[] = []; // To display messages from the backend

  constructor(private authService: AuthService, private router: Router) { }

  ngOnInit(): void {
  }

  login(): void {
    this.messages = []; // Clear previous messages
    this.authService.login(this.username, this.password).subscribe({
      next: (response) => {
        // Handle successful login, e.g., store token, redirect to dashboard
        console.log('Login successful');
        this.router.navigate(['/dashboard']);
      },
      error: (error) => {
        // Handle login errors, display messages
        console.error('Login failed', error);
        if (error.error && error.error.message) {
          this.messages.push({ severity: 'error', summary: 'Error', detail: error.error.message });
        } else {
          this.messages.push({ severity: 'error', summary: 'Error', detail: 'An unexpected error occurred during login.' });
        }
      }
    });
  }
}
