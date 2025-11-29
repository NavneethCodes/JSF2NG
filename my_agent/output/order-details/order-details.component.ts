import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { OrderService, Order, OrderItem } from '../order.service'; // Assuming OrderService and models exist
import { Message } from 'primeng/api'; // Import Message type for p-messages

@Component({
  selector: 'app-order-details',
  templateUrl: './order-details.component.html',
  styleUrls: ['./order-details.component.css']
})
export class OrderDetailsComponent implements OnInit {
  order: Order | null = null;
  orderId: string | null = null;
  messages: Message[] = [];

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private orderService: OrderService
  ) { }

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      this.orderId = params.get('orderId');
      if (this.orderId) {
        this.loadOrderDetails(this.orderId);
      } else {
        this.messages = [{ severity: 'error', summary: 'Error', detail: 'Order ID not provided.' }];
      }
    });
  }

  loadOrderDetails(id: string): void {
    this.orderService.getOrderById(id).subscribe(
      (orderData: Order) => {
        this.order = orderData;
      },
      error => {
        console.error('Error fetching order details:', error);
        this.messages = [{ severity: 'error', summary: 'Error', detail: 'Failed to load order details.' }];
      }
    );
  }

  goBack(): void {
    this.router.navigate(['/orders']); // Adjust the route as necessary
  }
}
