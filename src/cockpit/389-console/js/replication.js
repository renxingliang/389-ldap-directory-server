var repl_suffix = "";
var prev_repl_role_id ="";
var prev_repl_role ="";
var prev_rid = "";

function load_repl_jstree() {
  $('#repl-tree').jstree( {
    "plugins" : [ "wholerow" ]
  });
  
  // Set rid for each suffix if applicable
  prev_rid = "1";

  $('#repl-tree').on("changed.jstree", function (e, data) {
    console.log("The selected nodes are:");
    console.log(data.selected);
    repl_suffix = data.selected;
    if (repl_suffix == "repl-changelog-node") {
      $("#repl-changelog").show();
      $("#repl-splash").hide();
      $("#repl-config").hide();

      if ( $("#nsslapd-changelogdir").val() == "" ) {
        // Default value
        //$("#nsslapd-changelogdir").val("/var/lib/dirsrv/" + server_id + "/changelogdb");
      }
    } else if (repl_suffix == "repl-root") {
      $("#repl-changelog").hide();
      $("#repl-config").hide();
      $("#repl-splash").show();
    } else {
      // Suffix
      $("#repl-splash").hide();
      $("#repl-changelog").hide();
      $("#replica-header").html("Replication Configuration <font size='3'>(<b>" + repl_suffix + "</b>)</font>");
      // Check if this suffix is already setup for replication.  If so set the radio button, and populate the form
      $("#repl-config").show();
    }
  });
};

function clear_agmt_wizard () {
  // Clear input fields and reset dropboxes
  $('.ds-agmt-schedule-checkbox').prop('checked', true);
  $('#agmt-schedule-checkbox').prop('checked', true);
  $(".ds-wiz-input").val("");
  $("#agmt-start-time").val("");
  $("#agmt-end-time").val("");
  $(".ds-agmt-wiz-dropdown").prop('selectedIndex',0);
  $(".ds-accordion-panel").toggle("active");
  $(".ds-accordion-panel").css('display','none');
};

$(document).ready( function() {
  $("#repl-backend-selection").load("replication.html", function () {
    // Load the tree
    load_repl_jstree();
    $('#tree').on("changed.jstree", function (e, data) {
      console.log("The selected nodes are:");
      console.log(data.selected);
      var suffix = data.selected;
    });

    $("#set-default").on("click", function() {
      $("#nsslapd-changelogdir").val("/var/lib/dirsrv/" + server_id + "/changelogdb");
    });
    
    $("#nsds5replicaid").on("change", function() {
      prev_rid = $("#nsds5replicaid").val();
    });

    $(".repl-role").on("change", function() {
      var role = $("input[name=repl-role]:checked").val();
      if (role == "master" || role == "multi-master") {
         $("#nsds5replicaid").prop('required',true);
         $("#nsds5replicaid").prop('disabled', false);
         $("#nsds5replicaid").val(prev_rid);
      } else {
          $("#nsds5replicaid").prop('required',false);
          $("#nsds5replicaid").prop('disabled', true);
          if (role == "hub"){
            $("#nsds5replicaid").val("65535");
          } else {
            $("#nsds5replicaid").val("");    
          }
      }
      if (role == "no-repl") {
        // This also means disable replication: delete agmts, everything
        if (confirm("Are you sure you want to disable replication and remove all agreements?")){
           //delete everything
            $("#repl-form").hide();
        } else {
            //reset everything
            $("#" + prev_repl_role_id).prop("checked", true);
            if (prev_repl_role == "master" || prev_repl_role == "multi-master" ) {
              $("#nsds5replicaid").prop('required',true);
              $("#nsds5replicaid").prop('disabled', false);
              $("#nsds5replicaid").val(prev_rid);
            } else if (prev_repl_role == "hub") {
              $("#nsds5replicaid").val("65535");
            } else {
              // consumer
              $("#nsds5replicaid").val("");
            }
        }
       } else {
         $("#repl-form").show();
         prev_repl_role_id = this.id;
         prev_repl_role = role;
       }
    });

    // Set up agreement table
    $('#repl-agmt-table').DataTable( {
      "paging": true,
      "bAutoWidth": false,
      "dom": '<"pull-left"f><"pull-right"l>tip',
      //"lengthMenu": [ 16, 32, 64, 128],
      "language": {
        "emptyTable": "No agreements configured"
      },
      "columnDefs": [ {
        "targets": 4,
        "orderable": false
      } ]
    });

    // Set up CleanAllRUV Table
    $('#repl-clean-table').DataTable( {
      "paging": true,
      "bAutoWidth": false,
      "dom": '<"pull-left"f><"pull-right"l>tip',
      "language": {
        "emptyTable": "No agreements configured"
      },
      "columnDefs": [ {
        "targets": 3,
        "orderable": false
      } ]
    });

    $('#repl-summary-table').DataTable( {
      "paging": false,
      "searching": false,
      "bInfo" : false,
      "bAutoWidth": false,
      "dom": '<"pull-left"f><"pull-right"l>tip',
      "language": {
        "emptyTable": "No Replicated Suffixes"
      }
    });

    // Repl Agreement Wizard
    $("#agmt-close").on("click", function() {
      $("#agmt-form").css('display', 'none');
    });
    $("#agmt-cancel").on("click", function() {
      $("#agmt-form").css('display', 'none');
    });
    $("#create-agmt").on("click", function() {
      clear_agmt_wizard();
      $("#agmt-form").css('display', 'block');
    });

    // Handle disabling/enabling of agmt schedule panel
    $('#agmt-schedule-panel *').attr('disabled', true); /// Disabled by default
    $("#agmt-schedule-checkbox").change(function() {
      if(this.checked) {
        $('#agmt-schedule-panel *').attr('disabled', true);
      } else {
        $('#agmt-schedule-panel *').attr('disabled', false);
      }
    });

    // Based on the connection type change the agmt-auth options
    $("#nsds5replicatransportinfo").change(function() {
      var ldap_opts = {"Simple": "Simple",
                       "SASL/DIGEST-MD5": "SASL/DIGEST-MD5",
                       "SASL/GSSAPI": "SASL/GSSAPI"};
      var ldaps_opts = {"Simple": "Simple",
                        "SSL Client Authentication": "SSL Client Authentication",
                        "SASL/DIGEST-MD5": "SASL/DIGEST-MD5"};
      var $auth = $("#nsds5replicabindmethod");
      $auth.empty();
      var conn = $('#nsds5replicatransportinfo').val();
      if (conn == "LDAP"){
        $.each(ldap_opts, function(key, value) {
          $auth.append($("<option></option>").attr("value", value).text(key));
        });
      } else {
        // TLS options
        $.each(ldaps_opts, function(key, value) {
          $auth.append($("<option></option>").attr("value", value).text(key));
        });
      }
      $("#nsds5replicabinddn").prop('disabled', false);
      $("#nsds5replicacredentials").prop('disabled', false);
      $("#nsds5replicacredentials-confirm").prop('disabled', false);
    });

    // Check for auth changes and disable/enable bind DN & password
    $("#nsds5replicabindmethod").change(function() {
      var authtype = $('#nsds5replicabindmethod').val();
      if (authtype == "SSL Client Authentication") {
        $("#nsds5replicabinddn").prop('disabled', true);
        $("#nsds5replicacredentials").prop('disabled', true);
        $("#nsds5replicacredentials-confirm").prop('disabled', true);
      } else {
        $("#nsds5replicabinddn").prop('disabled', false);
        $("#nsds5replicacredentials").prop('disabled', false);
        $("#nsds5replicacredentials-confirm").prop('disabled', false);
      }
    });

    // Create time ticket for agmt schedule (start end times))
    $('input.timepicker').timepicker({
      'timeFormat': 'H:i',
      'disableTextInput': true
    });

    // Accordion opening/closings
    $(".ds-accordion-panel").css('display','none');
    var acc = document.getElementsByClassName("repl-accordion");
    for (var i = 0; i < acc.length; i++) {
      acc[i].onclick = function() {
        this.classList.toggle("active");
        var panel = this.nextElementSibling;
        /*if (panel.style.maxHeight && panel.style.maxHeight != "0px"){
          panel.style.maxHeight = null;
        } else {
          panel.style.maxHeight = panel.scrollHeight + "px";
        }*/
        if (panel.style.display == "block") {
            panel.style.display = "none";
        } else {
            panel.style.display = "block";
        }
      }
    }

    var repl_acc = document.getElementsByClassName("repl-config-accordion");
    for (var i = 0; i < repl_acc.length; i++) {
      repl_acc[i].onclick = function() {
        this.classList.toggle("active");
        var panel = this.nextElementSibling;
        if (panel.style.display == "block") {
            panel.style.display = "none";
        } else {
            panel.style.display = "block";
        }
      }
    }


  });
});
