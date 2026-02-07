---
description: Examples of MkDocs Material syntax including admonitions, tabbed code blocks, collapsible sections, and syntax highlighting.
---

# MKDocs Syntax Examples

## Syntax testing
```yaml title="test.yaml" linenums="1" hl_lines="2-3"
a:
  aa: "aa"
  ab: "ab"
b:
  ba: "ba"
  bb: "bb"
```

=== "Python"
    ```py
    def main():
        print("Hello world!")
    ```

=== "JavaScript"
    ```js
    console.log("Hello world")
    ```

!!! note "Note"
    This is a simple note.

!!! warning "Warning"
    This is a warning!

!!! danger "Danger!"
    This is dangerous!

??? info "Collapsible"
    This is an important text!