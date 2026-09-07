import { test, expect } from '@playwright/test';

test.describe('E2E User Stories', () => {
  test('US1: Automated Intake and Resolution', async ({ page }) => {
    // Navigate to employee portal
    await page.goto('/');
    
    // Employee starts chat
    await page.fill('input[type="text"]', 'I cannot connect to the VPN');
    await page.click('button:has-text("Send")');
    
    // Expect AI response verifying details
    await expect(page.locator('.message-ai')).toContainText('Let me check');
  });

  test('US2: Human Takeover and Escalation', async ({ page }) => {
    // Navigate to employee portal
    await page.goto('/');
    
    // Employee starts chat with hardware failure requiring escalation
    await page.fill('input[type="text"]', 'My laptop caught on fire');
    await page.click('button:has-text("Send")');
    
    // Ensure AI states escalation
    await expect(page.locator('.message-ai')).toContainText('escalating');
    
    // Open engineer dashboard
    await page.goto('/engineer');
    
    // Check if ticket is listed and click Take Over
    const ticketRow = page.locator('.ticket-item', { hasText: 'laptop caught on fire' });
    await expect(ticketRow).toBeVisible();
    await ticketRow.locator('button:has-text("Take Over")').click();
  });

  test('US3: Semantic Retrieval and Context', async ({ page }) => {
    // Open engineer dashboard
    await page.goto('/engineer');
    
    // Check for similar incidents displayed dynamically
    const similarIncidents = page.locator('.similar-incidents');
    await expect(similarIncidents.first()).toBeVisible();
  });
});
