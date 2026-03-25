# E-commerce Interaction Test Page - Expected Outcomes

## Overview
This document describes the expected behavior when the browser agent performs e-commerce tasks on the shop test pages.

## Pages

| Page | File | Description |
|------|------|-------------|
| Product Catalog | `index.html` | Main product listing |
| Shopping Cart | `cart.html` | Cart management |
| Checkout | `checkout.html` | Checkout form |

## Product Catalog Page

### Location
`test_pages/ecommerce/index.html`

### Products

| ID | Name | Price | Original Price | Category | Rating |
|----|------|-------|----------------|----------|--------|
| 1 | Wireless Headphones | $79.99 | $99.99 | electronics | 4.5 |
| 2 | Smart Watch | $199.99 | - | electronics | 4.8 |
| 3 | Laptop Stand | $39.99 | $49.99 | accessories | 4.3 |
| 4 | Bluetooth Speaker | $59.99 | - | electronics | 4.6 |
| 5 | Cotton T-Shirt | $24.99 | - | clothing | 4.2 |
| 6 | Denim Jeans | $49.99 | $69.99 | clothing | 4.4 |
| 7 | Sunglasses | $89.99 | - | accessories | 4.1 |
| 8 | Backpack | $69.99 | - | accessories | 4.7 |
| 9 | Desk Lamp | $34.99 | $44.99 | home | 4.5 |
| 10 | Plant Pot | $19.99 | - | home | 4.0 |
| 11 | Wireless Charger | $29.99 | - | electronics | 4.4 |
| 12 | Winter Jacket | $129.99 | $159.99 | clothing | 4.6 |

### Categories
- electronics (4 products)
- clothing (3 products)
- accessories (3 products)
- home (2 products)

## Shopping Cart Page

### Location
`test_pages/ecommerce/cart.html`

### Cart Operations

| Action | Method | Result |
|--------|--------|--------|
| Update quantity | `updateQuantity(productId, qty)` | Updates item quantity |
| Remove item | `removeFromCart(productId)` | Removes item from cart |
| Clear cart | `clearCart()` | Removes all items |

### Pricing Rules

| Item | Calculation |
|------|-------------|
| Subtotal | Sum of (price × quantity) for all items |
| Shipping | FREE if subtotal > $50, otherwise $5.99 |
| Tax | 8% of subtotal |
| Total | subtotal + shipping + tax |

## Checkout Page

### Location
`test_pages/ecommerce/checkout.html`

### Form Fields

| Section | Field | Required | Validation |
|---------|-------|----------|------------|
| Contact | email | Yes | Valid email format |
| Contact | phone | No | - |
| Shipping | firstName | Yes | Non-empty |
| Shipping | lastName | Yes | Non-empty |
| Shipping | address | Yes | Non-empty |
| Shipping | city | Yes | Non-empty |
| Shipping | state | Yes | Must select |
| Shipping | zip | Yes | Non-empty |
| Payment | cardNumber | Yes | 13+ digits |
| Payment | expiry | Yes | MM/YY format |
| Payment | cvv | Yes | 3+ digits |
| Payment | cardName | Yes | Non-empty |

### Order Flow

```
1. Add items to cart (index.html)
2. Go to cart (cart.html)
3. Review items, update quantities
4. Proceed to checkout (checkout.html)
5. Fill shipping information
6. Fill payment information
7. Place order
8. Success modal appears
9. Cart is cleared
```

## Testing Scenarios

### Scenario 1: Add to Cart
**Task:** "Add Wireless Headphones to cart"

**Steps:**
1. Find product card for "Wireless Headphones"
2. Set quantity to 1
3. Click "Add to Cart" button

**Expected Result:**
- Button shows "Added!"
- Cart count increases
- Notification shows "Wireless Headphones added to cart!"
- `itemAddedToCart` event dispatched

### Scenario 2: Complete Purchase Flow
**Task:** "Buy a Smart Watch"

**Steps:**
1. Add Smart Watch to cart
2. Click cart button
3. Review cart
4. Click "Proceed to Checkout"
5. Fill all required fields
6. Click "Place Order"

**Expected Result:**
- Success modal appears
- Order number displayed
- Cart cleared
- `orderPlaced` event dispatched

### Scenario 3: Update Cart Quantity
**Task:** "Add 2 more Laptop Stands"

**Steps:**
1. Add Laptop Stand to cart
2. Go to cart page
3. Change quantity to 3
4. Verify total updated

**Expected Result:**
- Quantity shows 3
- Item total = $39.99 × 3 = $119.97
- Cart totals recalculated

### Scenario 4: Remove from Cart
**Task:** "Remove item from cart"

**Steps:**
1. Have items in cart
2. Click "Remove" on an item

**Expected Result:**
- Item removed from list
- Notification shows "Item removed from cart"
- Totals recalculated
- `itemRemovedFromCart` event dispatched

### Scenario 5: Filter Products
**Task:** "Show only electronics"

**Steps:**
1. Select "electronics" from category dropdown
2. Verify only electronics shown

**Expected Result:**
- 4 products displayed (Headphones, Watch, Speaker, Charger)
- All have category "electronics"

### Scenario 6: Search Products
**Task:** "Search for 'watch'"

**Steps:**
1. Type "watch" in search box
2. Press Enter or click Search

**Expected Result:**
- Smart Watch displayed
- Other products hidden

### Scenario 7: Checkout Validation
**Task:** "Submit checkout with empty fields"

**Steps:**
1. Go to checkout with items in cart
2. Leave required fields empty
3. Click "Place Order"

**Expected Result:**
- Form not submitted
- Error messages appear for empty fields
- Error styling on invalid inputs

## CSS Selectors Reference

### Product Catalog
```css
.product-card
.product-card[data-product-id="X"]
.product-name
.current-price
.original-price
.stars
.add-to-cart-btn
.qty-input
.qty-btn
#cartCount
#categoryFilter
#sortFilter
#searchInput
```

### Cart Page
```css
.cart-item
.cart-item[data-item-id="X"]
.item-name
.item-price
.item-quantity
.qty-input
.qty-btn
.remove-btn
.item-total-price
.checkout-btn
```

### Checkout Page
```css
#email
#phone
#firstName
#lastName
#address
#city
#state
#zip
#cardNumber
#expiry
#cvv
#cardName
#placeOrderBtn
.success-modal
.order-number
```

## JavaScript Testing Helpers

### Product Catalog
```javascript
window.products          // All products array
window.addToCart(productId, quantity)
window.getCart()         // Get cart from localStorage
window.clearCart()
window.ecommercePageLoaded
```

### Cart Page
```javascript
window.updateQuantity(productId, newQty)
window.removeFromCart(productId)
window.getCart()
window.clearCart()
window.cartPageLoaded
```

### Checkout Page
```javascript
window.validateForm()    // Returns boolean
window.placeOrder()      // Submit order
window.calculateTotals() // Returns { subtotal, shipping, tax, total }
window.checkoutPageLoaded
```

## Custom Events

| Event | Trigger | Detail |
|-------|---------|--------|
| `ecommercePageReady` | Catalog loaded | None |
| `cartPageReady` | Cart page loaded | None |
| `checkoutPageReady` | Checkout loaded | None |
| `itemAddedToCart` | Item added | `{ product, quantity }` |
| `itemRemovedFromCart` | Item removed | `{ productId }` |
| `cartUpdated` | Quantity changed | `cart` array |
| `orderPlaced` | Order completed | `{ orderNumber, total }` |

## Local Storage

| Key | Type | Description |
|-----|------|-------------|
| `cart` | JSON string | Array of cart items |

### Cart Item Structure
```json
{
    "id": 1,
    "name": "Wireless Headphones",
    "price": 79.99,
    "quantity": 2
}
```

## Pricing Examples

### Example 1: Single Item
- Item: Wireless Headphones × 1 = $79.99
- Subtotal: $79.99
- Shipping: FREE (over $50)
- Tax (8%): $6.40
- **Total: $86.39**

### Example 2: Multiple Items
- Item: Cotton T-Shirt × 2 = $49.98
- Item: Desk Lamp × 1 = $34.99
- Subtotal: $84.97
- Shipping: FREE
- Tax (8%): $6.80
- **Total: $91.77**

### Example 3: Small Order
- Item: Plant Pot × 1 = $19.99
- Subtotal: $19.99
- Shipping: $5.99
- Tax (8%): $1.60
- **Total: $27.58**

## Form Validation Rules

### Email
- Pattern: `^[^\s@]+@[^\s@]+\.[^\s@]+$`
- Example valid: `user@example.com`
- Example invalid: `user@`, `@example.com`

### Card Number
- Remove spaces before validation
- Must be 13+ digits
- Auto-format with spaces every 4 digits

### Expiry Date
- Format: MM/YY
- Auto-add slash after 2 digits
- Example: `12/25`

### CVV
- 3-4 digits
- Example: `123`

## Automation Tips

1. **Wait for page load:** Check `window.ecommercePageLoaded`, `window.cartPageLoaded`, `window.checkoutPageLoaded`
2. **Verify cart state:** Check `localStorage.getItem('cart')`
3. **Handle modal:** Wait for `.success-modal.visible`
4. **Check cart count:** Read `#cartCount` text
5. **Verify totals:** Compare with calculated values
