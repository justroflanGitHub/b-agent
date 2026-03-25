/**
 * Form Validation Script for Contact Form Test Page
 * Provides client-side validation for testing browser agent capabilities
 */

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('contactForm');
    const submitBtn = document.getElementById('submitBtn');
    const resetBtn = document.getElementById('resetBtn');
    const successMessage = document.getElementById('successMessage');
    
    // Form fields
    const fields = {
        firstName: {
            element: document.getElementById('firstName'),
            error: document.getElementById('firstNameError'),
            validate: (value) => value.trim().length >= 1,
            errorMessage: 'Please enter your first name'
        },
        lastName: {
            element: document.getElementById('lastName'),
            error: document.getElementById('lastNameError'),
            validate: (value) => value.trim().length >= 1,
            errorMessage: 'Please enter your last name'
        },
        email: {
            element: document.getElementById('email'),
            error: document.getElementById('emailError'),
            validate: (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
            errorMessage: 'Please enter a valid email address'
        },
        username: {
            element: document.getElementById('username'),
            error: document.getElementById('usernameError'),
            validate: (value) => /^[a-zA-Z0-9]{3,20}$/.test(value),
            errorMessage: 'Username must be 3-20 characters (letters and numbers only)'
        },
        password: {
            element: document.getElementById('password'),
            error: document.getElementById('passwordError'),
            validate: (value) => value.length >= 8,
            errorMessage: 'Password must be at least 8 characters'
        },
        confirmPassword: {
            element: document.getElementById('confirmPassword'),
            error: document.getElementById('confirmPasswordError'),
            validate: (value) => value === document.getElementById('password').value,
            errorMessage: 'Passwords do not match'
        },
        subject: {
            element: document.getElementById('subject'),
            error: document.getElementById('subjectError'),
            validate: (value) => value !== '',
            errorMessage: 'Please select a subject'
        },
        message: {
            element: document.getElementById('message'),
            error: document.getElementById('messageError'),
            validate: (value) => value.trim().length >= 10,
            errorMessage: 'Please enter a message (minimum 10 characters)'
        },
        terms: {
            element: document.getElementById('terms'),
            error: document.getElementById('termsError'),
            validate: () => document.getElementById('terms').checked,
            errorMessage: 'You must agree to the terms'
        }
    };
    
    // Password strength indicator
    const passwordField = document.getElementById('password');
    const strengthBar = document.getElementById('passwordStrengthBar');
    
    passwordField.addEventListener('input', function() {
        const password = this.value;
        let strength = 0;
        
        if (password.length >= 8) strength++;
        if (password.length >= 12) strength++;
        if (/[A-Z]/.test(password)) strength++;
        if (/[a-z]/.test(password)) strength++;
        if (/[0-9]/.test(password)) strength++;
        if (/[^A-Za-z0-9]/.test(password)) strength++;
        
        strengthBar.className = 'password-strength-bar';
        if (strength <= 2) {
            strengthBar.classList.add('weak');
        } else if (strength <= 4) {
            strengthBar.classList.add('medium');
        } else {
            strengthBar.classList.add('strong');
        }
    });
    
    // Budget range slider
    const budgetSlider = document.getElementById('budget');
    const budgetValue = document.getElementById('budgetValue');
    
    budgetSlider.addEventListener('input', function() {
        budgetValue.textContent = '$' + this.value;
    });
    
    // Real-time validation on blur
    Object.keys(fields).forEach(fieldName => {
        const field = fields[fieldName];
        if (field.element) {
            field.element.addEventListener('blur', function() {
                validateField(fieldName);
            });
            
            field.element.addEventListener('input', function() {
                // Clear error on input
                if (field.error) {
                    field.error.classList.remove('visible');
                }
                field.element.classList.remove('error');
            });
        }
    });
    
    // Validate single field
    function validateField(fieldName) {
        const field = fields[fieldName];
        if (!field || !field.element) return true;
        
        const value = field.element.type === 'checkbox' ? field.element.checked : field.element.value;
        const isValid = field.validate(value);
        
        if (!isValid) {
            field.element.classList.add('error');
            if (field.error) {
                field.error.textContent = field.errorMessage;
                field.error.classList.add('visible');
            }
        } else {
            field.element.classList.remove('error');
            if (field.error) {
                field.error.classList.remove('visible');
            }
        }
        
        return isValid;
    }
    
    // Validate all fields
    function validateForm() {
        let isValid = true;
        
        Object.keys(fields).forEach(fieldName => {
            if (!validateField(fieldName)) {
                isValid = false;
            }
        });
        
        return isValid;
    }
    
    // Form submission
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        if (validateForm()) {
            // Collect form data
            const formData = {
                firstName: document.getElementById('firstName').value,
                lastName: document.getElementById('lastName').value,
                email: document.getElementById('email').value,
                phone: document.getElementById('phone').value,
                birthdate: document.getElementById('birthdate').value,
                username: document.getElementById('username').value,
                subject: document.getElementById('subject').value,
                contactMethod: document.querySelector('input[name="contactMethod"]:checked').value,
                bestTimes: Array.from(document.querySelectorAll('input[name="bestTime"]:checked')).map(cb => cb.value),
                website: document.getElementById('website').value,
                budget: document.getElementById('budget').value,
                priority: document.getElementById('priority').value,
                quantity: document.getElementById('quantity').value,
                message: document.getElementById('message').value,
                interests: Array.from(document.querySelectorAll('input[name="interests"]:checked')).map(cb => cb.value),
                newsletter: document.getElementById('newsletter').checked,
                terms: document.getElementById('terms').checked,
                timestamp: new Date().toISOString()
            };
            
            // Log form data (for testing purposes)
            console.log('Form submitted successfully:', formData);
            
            // Show success message
            successMessage.classList.add('visible');
            
            // Disable submit button
            submitBtn.disabled = true;
            submitBtn.textContent = 'Submitted!';
            
            // Store form data in sessionStorage for verification
            sessionStorage.setItem('lastFormData', JSON.stringify(formData));
            
            // Dispatch custom event for testing
            window.dispatchEvent(new CustomEvent('formSubmitted', { detail: formData }));
        } else {
            // Scroll to first error
            const firstError = form.querySelector('.error');
            if (firstError) {
                firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                firstError.focus();
            }
        }
    });
    
    // Reset button
    resetBtn.addEventListener('click', function() {
        form.reset();
        successMessage.classList.remove('visible');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Form';
        
        // Clear all error states
        Object.keys(fields).forEach(fieldName => {
            const field = fields[fieldName];
            if (field.element) {
                field.element.classList.remove('error');
            }
            if (field.error) {
                field.error.classList.remove('visible');
            }
        });
        
        // Reset password strength bar
        strengthBar.className = 'password-strength-bar';
        
        // Reset budget display
        budgetValue.textContent = '$5000';
        
        // Clear session storage
        sessionStorage.removeItem('lastFormData');
        
        // Dispatch custom event for testing
        window.dispatchEvent(new CustomEvent('formReset'));
    });
    
    // Expose validation function for testing
    window.validateForm = validateForm;
    window.validateField = validateField;
    window.getFormData = function() {
        return JSON.parse(sessionStorage.getItem('lastFormData') || 'null');
    };
    
    // Mark page as loaded for testing
    window.formPageLoaded = true;
    window.dispatchEvent(new CustomEvent('formPageReady'));
});

// Helper function to fill form programmatically (for testing)
window.fillForm = function(data) {
    if (data.firstName) document.getElementById('firstName').value = data.firstName;
    if (data.lastName) document.getElementById('lastName').value = data.lastName;
    if (data.email) document.getElementById('email').value = data.email;
    if (data.phone) document.getElementById('phone').value = data.phone;
    if (data.birthdate) document.getElementById('birthdate').value = data.birthdate;
    if (data.username) document.getElementById('username').value = data.username;
    if (data.password) document.getElementById('password').value = data.password;
    if (data.confirmPassword) document.getElementById('confirmPassword').value = data.confirmPassword;
    if (data.subject) document.getElementById('subject').value = data.subject;
    if (data.contactMethod) {
        document.querySelector(`input[name="contactMethod"][value="${data.contactMethod}"]`).checked = true;
    }
    if (data.bestTimes) {
        data.bestTimes.forEach(time => {
            const checkbox = document.querySelector(`input[name="bestTime"][value="${time}"]`);
            if (checkbox) checkbox.checked = true;
        });
    }
    if (data.website) document.getElementById('website').value = data.website;
    if (data.budget) {
        document.getElementById('budget').value = data.budget;
        document.getElementById('budgetValue').textContent = '$' + data.budget;
    }
    if (data.priority) document.getElementById('priority').value = data.priority;
    if (data.quantity) document.getElementById('quantity').value = data.quantity;
    if (data.message) document.getElementById('message').value = data.message;
    if (data.interests) {
        data.interests.forEach(interest => {
            const checkbox = document.querySelector(`input[name="interests"][value="${interest}"]`);
            if (checkbox) checkbox.checked = true;
        });
    }
    if (data.newsletter !== undefined) document.getElementById('newsletter').checked = data.newsletter;
    if (data.terms !== undefined) document.getElementById('terms').checked = data.terms;
};

// Submit form programmatically (for testing)
window.submitForm = function() {
    document.getElementById('contactForm').dispatchEvent(new Event('submit'));
};
