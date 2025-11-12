# Scale Operations - Quick Start Guide

5-minute visual guide to get started with Scale Operations.

## Step 1: Open Scale Operations (30 seconds)

![Getting Started](tutorial-01-getting-started.png)

**Action**: Click the "Scale Operations" tab in the top navigation bar.

---

## Step 2: Choose Operation Mode (30 seconds)

**Scale-Up**: Add test resources
- Use for load testing
- Use for validation
- Use for testing resilience

**Scale-Down**: Remove resources
- Use for cleanup
- Use for graph reduction
- Use for testing removal

**Recommended for first time**: Choose **SCALE UP**

---

## Step 3: Configure Strategy (1 minute)

![Template Strategy](tutorial-02-template-strategy.png)

**Easiest option**: Template-Based strategy
1. Select "Template-Based" from Strategy dropdown
2. Choose a template file (default: `templates/scale_up_template.yaml`)
3. Set scale factor to **2x** (doubles resources)

---

## Step 4: Enable Validation (10 seconds)

![Scale Factor](tutorial-04-scale-factor.png)

**Action**: Check "Run validation before and after operation"

**Why**: Catches issues before they become problems.

---

## Step 5: Preview First (30 seconds)

![Preview & Execute](tutorial-05-preview-execute.png)

**CRITICAL**: Always click **PREVIEW** before **EXECUTE**

**Preview shows:**
- What will be created
- How many nodes/relationships
- No changes are made (safe)

---

## Step 6: Execute (10 seconds)

**Action**: Click **EXECUTE** button

**What happens:**
- Resources are created in graph
- Progress shown in real-time
- Validation runs automatically

**Wait**: For completion message

---

## Step 7: View Results (30 seconds)

![Quick Actions](tutorial-06-quick-actions.png)

**Use Quick Actions:**
- **STATS**: View what was created
- **VALIDATE**: Verify integrity
- **CLEAN**: Remove when done testing

---

## Complete First Workflow

**Total time**: ~5 minutes

```
1. Click "Scale Operations" tab
2. Select "SCALE UP" mode
3. Keep "Template-Based" strategy (default)
4. Set scale factor to 2x
5. Enable validation checkbox
6. Click PREVIEW button
7. Review preview output
8. Click EXECUTE button
9. Wait for completion
10. Click STATS to see results
```

---

## Common Mistakes to Avoid

### Mistake 1: Executing Without Preview
**Problem**: No visibility into what will change
**Solution**: Always click PREVIEW first

### Mistake 2: Using High Scale Factors Initially
**Problem**: Creates too many resources, hard to understand
**Solution**: Start with 2x, then increase gradually

### Mistake 3: Forgetting to Clean Up
**Problem**: Graph fills with test data
**Solution**: Use CLEAN button after each test session

### Mistake 4: Skipping Validation
**Problem**: Issues go undetected
**Solution**: Always enable "Run validation before and after"

---

## Next Steps

After your first successful operation:

### Learn More Strategies
- **Tutorial 3**: Scenario-Based (realistic architectures)
- **Tutorial 8**: Scale-Down mode (resource removal)

### Master Advanced Features
- **Tutorial 7**: Validation options
- Configure pre/post validation
- Understand integrity checks

### Explore Workflows
- **README.md**: Complete tutorial guide
- 4 detailed workflows
- Best practices and tips

---

## Troubleshooting

### Problem: Preview shows no changes
**Solution**: Check that Tenant ID is set correctly

### Problem: Execute button is disabled
**Solution**: Run Preview first, fix any validation errors

### Problem: Operation seems stuck
**Solution**: Check backend connection status (yellow warning at top)

### Problem: Too many resources created
**Solution**: Use CLEAN button, then retry with lower scale factor

---

## Key Shortcuts

| Action | Steps |
|--------|-------|
| Quick test | Scale-Up → Template → 2x → Preview → Execute |
| View results | Quick Actions → STATS |
| Clean up | Quick Actions → CLEAN |
| Verify integrity | Quick Actions → VALIDATE |

---

## Pro Tips

1. **Start small**: Use scale factor 2x first
2. **Always preview**: Never execute blind
3. **Enable validation**: Catches issues early
4. **Clean regularly**: Keeps graph focused
5. **Check stats**: Understand operation impact

---

## Help

Need more detail?
- **README.md**: Full tutorial with explanations
- **TUTORIAL_INDEX.md**: Visual index of all tutorials
- **TUTORIAL_SUMMARY.md**: Overview and technical details

Questions?
- Check `/docs/SCALE_OPERATIONS_SPECIFICATION.md`
- Review `/docs/SCALE_OPERATIONS_INDEX.md`
- Refer to project `CLAUDE.md`

---

**Remember**: Preview → Validate → Execute → Clean

That's the safe workflow for Scale Operations!
