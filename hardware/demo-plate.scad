// Concept only: synthetic demo board. Dimensions are placeholders, not fabrication approval.
// Recipe coordinates are in mm; validate board view/mirroring and receiver dimensions first.
plate_width = 70;
plate_height = 70;
plate_thickness = 4;
board_margin = 10;
pogo_hole_diameter = 1.5;
mount_hole_diameter = 3.2;
mount_inset = 5;
demo_points = [
    [10,10], [20,10], [30,10], [40,10],
    [10,20], [20,20], [30,20], [40,20],
    [10,30], [20,30], [30,30], [40,30],
    [10,40], [20,40], [30,40], [40,40]
];
$fn = 40;
difference() {
    cube([plate_width, plate_height, plate_thickness]);
    for (point = demo_points)
        translate([board_margin + point[0], board_margin + point[1], -1])
            cylinder(h=plate_thickness+2, d=pogo_hole_diameter);
    for (x = [mount_inset, plate_width-mount_inset])
        for (y = [mount_inset, plate_height-mount_inset])
            translate([x,y,-1]) cylinder(h=plate_thickness+2, d=mount_hole_diameter);
}
