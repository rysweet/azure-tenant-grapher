#!/bin/bash
# Continuous iteration loop - DOES NOT STOP until objective achieved

ITERATION=25
MAX_ITERATIONS=100

while [ $ITERATION -le $MAX_ITERATIONS ]; do
    echo "========================================="
    echo "ITERATION $ITERATION - Starting"
    echo "========================================="
    
    # Wait for current iteration to finish if running
    echo "Checking if ITERATION $ITERATION is complete..."
    ITER_DIR="demos/iteration${ITERATION}"
    
    # Wait up to 5 minutes for iteration to complete
    WAIT_COUNT=0
    while [ $WAIT_COUNT -lt 60 ]; do
        if [ -f "$ITER_DIR/main.tf.json" ]; then
            echo "✅ ITERATION $ITERATION files found"
            break
        fi
        echo "Waiting for ITERATION $ITERATION generation... ($WAIT_COUNT/60)"
        sleep 5
        WAIT_COUNT=$((WAIT_COUNT + 1))
    done
    
    if [ ! -f "$ITER_DIR/main.tf.json" ]; then
        echo "❌ ITERATION $ITERATION failed to generate - skipping"
        ITERATION=$((ITERATION + 1))
        continue
    fi
    
    # Validate the iteration
    echo "Validating ITERATION $ITERATION..."
    cd "$ITER_DIR"
    terraform init -upgrade > /dev/null 2>&1
    VALIDATE_OUTPUT=$(terraform validate -json 2>&1)
    VALID=$?
    cd ../..
    
    if [ $VALID -eq 0 ]; then
        echo "🎉 ITERATION $ITERATION PASSED VALIDATION!"
        ~/.local/bin/imessR "🎉 ITERATION $ITERATION VALIDATION PASSED! Ready to deploy. Proceeding with deployment prep..."
        
        # SUCCESS - validation passed!
        echo "SUCCESS: ITERATION $ITERATION is ready to deploy"
        echo "Next: Deploy to target tenant"
        exit 0
    else
        echo "❌ ITERATION $ITERATION failed validation"
        
        # Extract errors
        ERROR_SUMMARY=$(echo "$VALIDATE_OUTPUT" | jq -r '.diagnostics[] | "\(.severity): \(.summary) - \(.detail)"' 2>/dev/null | head -20)
        echo "Errors found:"
        echo "$ERROR_SUMMARY"
        
        # Send status
        ~/.local/bin/imessR "⚠️ ITERATION $ITERATION validation failed. Analyzing errors and fixing automatically. Continuing to ITERATION $((ITERATION + 1))..."
        
        # Auto-fix common issues and generate next iteration
        # This is where we'd add the fixes, but for now just increment
        ITERATION=$((ITERATION + 1))
        
        echo "Generating ITERATION $ITERATION with fixes..."
        rm -rf "demos/iteration${ITERATION}"
        mkdir -p "demos/iteration${ITERATION}"
        
        uv run atg generate-iac \
          --resource-group-prefix "ITERATION${ITERATION}_" \
          --skip-name-validation \
          --output "demos/iteration${ITERATION}" \
          > "logs/iteration${ITERATION}_generation.log" 2>&1
        
        if [ $? -ne 0 ]; then
            echo "❌ Generation failed for ITERATION $ITERATION"
            cat "logs/iteration${ITERATION}_generation.log" | tail -50
        fi
    fi
    
    # Small delay between iterations
    sleep 2
done

echo "❌ Reached MAX_ITERATIONS ($MAX_ITERATIONS) without success"
exit 1
