import { test, expect } from '@playwright/test';

test.describe('Dashboard Navigation', () => {
  test.beforeEach(async ({ page }) => {
    // 1. Always use semantic navigation
    await page.goto('/dashboard');
  });

  test('should display user projects', async ({ page }) => {
    // 2. Use getByRole for accessibility-first testing
    const heading = page.getByRole('heading', { name: 'Your Projects' });
    await expect(heading).toBeVisible();

    // 3. Use data-testid for stable targeting of specific elements
    const projectList = page.getByTestId('project-list');
    await expect(projectList).toBeVisible();

    // 4. Web-first assertions handle auto-waiting
    const firstProject = projectList.locator('li').first();
    await expect(firstProject).toContainText('Paperclip Core');
  });

  test('should open project creation modal', async ({ page }) => {
    await page.getByRole('button', { name: 'New Project' }).click();
    
    // 5. Verify modal state
    const modal = page.getByRole('dialog');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText('Create New Project');
  });
});
