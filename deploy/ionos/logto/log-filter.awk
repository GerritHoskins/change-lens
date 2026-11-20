# Logto's output passes through this filter before Docker stores it (compose.yaml, LR-12). Logto prints
# every request line with its query string, which carries the email address and the one-time sign-in token:
#   <id>   <-- GET /sign-in?login_hint=...&one_time_token=...
# The filter drops the query string of a request and masks any email address, plain or URL-encoded.
# Each line is written at once: a buffered filter would hold Logto's last lines back.
{
    out = ""
    while (match($0, /(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) [^ ?]*[?][^ ]*/)) {
        request = substr($0, RSTART, RLENGTH)
        sub(/[?].*/, "?[removed]", request)
        out = out substr($0, 1, RSTART - 1) request
        $0 = substr($0, RSTART + RLENGTH)
    }
    $0 = out $0
    gsub(/[A-Za-z0-9._%+-]+(@|%40)[A-Za-z0-9-]+([.][A-Za-z0-9-]+)+/, "[email]")
    print
    fflush()
}
