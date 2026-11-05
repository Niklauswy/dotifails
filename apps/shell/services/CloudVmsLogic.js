.pragma library

// Pure helpers of the Cloud VMs bar item (services/CloudVms.qml); tested with node
// (tests/shell_bridge/test_cloud_logic.py). The state is the JSON of
// $XDG_RUNTIME_DIR/wysun-cloud/state.json (apps/python/wysun_cloud/state.py).

var STALE = 600;  // `wysun cloud --estado` refreshes the file every 2 min; older is unknown

// Running VMs of a state written no more than STALE seconds ago; anything malformed is ignored.
function running(state, nowSec) {
    if (!state || typeof state !== "object" || typeof state.updated !== "number")
        return [];
    if (nowSec - state.updated > STALE)
        return [];
    var list = Array.isArray(state.running) ? state.running : [];
    return list.filter(function (vm) {
        return vm && typeof vm.project === "string" && typeof vm.name === "string" && typeof vm.zone === "string";
    });
}

// Tooltip text: one line per project, «proyecto: a, b».
function tooltip(list) {
    var order = [], groups = {};
    (list || []).forEach(function (vm) {
        if (!vm || typeof vm.project !== "string" || typeof vm.name !== "string")
            return;
        if (!groups[vm.project]) {
            groups[vm.project] = [];
            order.push(vm.project);
        }
        groups[vm.project].push(vm.name);
    });
    return order.map(function (project) {
        return project + ": " + groups[project].join(", ");
    }).join("\n");
}

function label(list) {
    return String((list || []).length);
}
