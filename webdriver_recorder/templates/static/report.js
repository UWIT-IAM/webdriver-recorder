
const expandIconClass = "bi-chevron-bar-expand";
const collapseIconClass = "bi-chevron-bar-contract";
const collapseHideEvent = new Event('hide.bs.collapse');
const collapseShowEvent = new Event('show.bs.collapse');

function zoomToAnchor() {
    // When called, will expand a test case that is include in the URL
    // as an anchor. e.g., "index.html#test_foo-test_bar-baz" would
    // expand the "test_foo-test_bar-baz-collapse" element,
    // then scroll it into view.
    let anchor = window.location.hash.substr(1);
    if (anchor) {
        let element = document.getElementById(anchor + "-collapse");
        bootstrap.Collapse.getOrCreateInstance(element, { toggle: true}).show();
        element.scrollIntoView();
    }
}

function bindFailureToggleEvents() {
    let showFailuresToggle = document.getElementById('show-failures-slider')
    if (showFailuresToggle !== null) {
        showFailuresToggle.addEventListener('change', function(event) {
            let elements  = [].slice.call(
                document.querySelectorAll('.result-success')
            );
            let showElement = !this.checked;  // 'checked' means 'do not show successes'
            elements.map(function(e) {
                e.classList.toggle('show', showElement);
            });
        });
    }
}

function toggleElementCollapse(element, state) {
    let instance = bootstrap.Collapse.getOrCreateInstance(element, {toggle: state});
    if (state) {
        instance.show();
    } else {
        instance.hide();
    }
}

function collapseAll(elementList) {
    elementList.map(function(e) {
        toggleElementCollapse(e, false)}
    );
}

function expandAll(elementList) {
    elementList.map(function(e) {
        toggleElementCollapse(e, true)}
    );
}

function bindCollapseEvents() {
    let collapseContainerList  = [].slice.call(
        document.querySelectorAll('.collapse')
    );
    collapseAll(collapseContainerList);

    let collapseAllElement = document.getElementById('collapse-all');
    let expandAllElement = document.getElementById('expand-all');

    expandAllElement.addEventListener('click', function() {
        expandAll(collapseContainerList);
    });

    collapseAllElement.addEventListener('click', function() {
        collapseAll(collapseContainerList);
    });

    collapseContainerList.map(function(element) {
        let collapseIcon = element.parentElement
            .getElementsByClassName('collapse-toggle-icon')[0];
        let collapseAnchor = element.parentElement
            .getElementsByClassName('collapse-toggle-anchor')[0];
        element.addEventListener('shown.bs.collapse', function() {
            collapseIcon.classList.replace(expandIconClass, collapseIconClass);
            collapseAnchor.setAttribute('title', 'Collapse');
        })
        element.addEventListener('hidden.bs.collapse', function() {
            collapseIcon.classList.replace(collapseIconClass, expandIconClass);
            collapseAnchor.setAttribute('title', 'Expand');
        })
    });
}

function copyToClipboard(value, target) {
    // Copies the given value to the user's clipboard.
    // Optionally accepts `target: string` which can be HTML,
    // which provides details on what was copied. See example
    // use in toast.html
    navigator.clipboard.writeText(value);
    let toastElement = document.getElementById('toast-clipboard-toast');
    let toastTargetElement = document.getElementById('clipboard-copy-target');
    let toastValueElement = document.getElementById('clipboard-copy-value');
    let toast = bootstrap.Toast.getOrCreateInstance(toastElement);
    target = target ? target : "";
    toastValueElement.innerHTML = value;
    toastTargetElement.innerHTML = target;
    toast.show();
}

function copyUrlToClipboard(path) {
    let url = window.location + path
    copyToClipboard(url, 'URL');
}

document.addEventListener("DOMContentLoaded", function(event) {
    bindFailureToggleEvents();
    bindCollapseEvents();
    zoomToAnchor();
});
