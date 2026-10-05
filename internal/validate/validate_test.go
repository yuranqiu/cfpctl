package validate

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"testing/fstest"
)

const validConference = `- name: Example
  slug: example
  fields: [security]
  homepage: https://example.org/
  cycles:
    - name: '2027'
      deadline: '2027-01-01T23:59:59-12:00'
`

func TestValidateFS(t *testing.T) {
	tests := []struct {
		name                 string
		files                fstest.MapFS
		wantError            string
		wantFiles, wantConfs int
	}{
		{"valid", fstest.MapFS{"security.yaml": {Data: []byte(validConference)}}, "", 1, 1},
		{"no files", fstest.MapFS{}, "no YAML data files", 0, 0},
		{"no root YAML", fstest.MapFS{"README.md": {Data: []byte("docs")}, "nested/security.yaml": {Data: []byte(validConference)}}, "no YAML data files", 0, 0},
		{"empty YAML", fstest.MapFS{"security.yaml": {}}, "at least one conference", 1, 0},
		{"comment only", fstest.MapFS{"security.yaml": {Data: []byte("# no conferences\n")}}, "at least one conference", 1, 0},
		{"empty list", fstest.MapFS{"security.yaml": {Data: []byte("[]")}}, "at least one conference", 1, 0},
		{"malformed", fstest.MapFS{"security.yaml": {Data: []byte("- name: [")}}, "parse error", 1, 0},
		{"duplicate across files", fstest.MapFS{"a.yaml": {Data: []byte(validConference)}, "b.yaml": {Data: []byte(validConference)}}, "duplicate slug", 2, 2},
		{"duplicate within file", fstest.MapFS{"a.yaml": {Data: []byte(validConference + validConference)}}, "duplicate slug", 1, 2},
		{"empty file alongside valid", fstest.MapFS{"a.yaml": {Data: []byte(validConference)}, "b.yaml": {}}, "at least one conference", 2, 1},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := ValidateFS(tt.files)
			if result.TotalFiles != tt.wantFiles || result.TotalConfs != tt.wantConfs {
				t.Fatalf("counts = (%d, %d), want (%d, %d)", result.TotalFiles, result.TotalConfs, tt.wantFiles, tt.wantConfs)
			}
			if tt.wantError == "" {
				if len(result.Errors) != 0 {
					t.Fatal(result.Summary())
				}
			} else if len(result.Errors) == 0 || !strings.Contains(result.Summary(), tt.wantError) {
				t.Fatalf("expected %q error, got %s", tt.wantError, result.Summary())
			}
		})
	}
}

func TestValidateDir(t *testing.T) {
	dir := t.TempDir()
	if result := ValidateDir(filepath.Join(dir, "missing")); len(result.Errors) == 0 {
		t.Fatal("missing directory passed validation")
	}
	if result := ValidateDir(dir); len(result.Errors) == 0 {
		t.Fatal("empty directory passed validation")
	}
	filename := filepath.Join(dir, "security.yaml")
	if err := os.WriteFile(filename, []byte(validConference), 0600); err != nil {
		t.Fatal(err)
	}
	if result := ValidateDir(dir); len(result.Errors) != 0 || result.TotalConfs != 1 {
		t.Fatal(result.Summary())
	}
	if result := ValidateDir(filename); len(result.Errors) == 0 {
		t.Fatal("regular file passed directory validation")
	}
}

func TestValidateAll(t *testing.T) {
	result := ValidateAll()
	if result.TotalConfs == 0 || len(result.Errors) != 0 {
		t.Fatal(result.Summary())
	}
}
