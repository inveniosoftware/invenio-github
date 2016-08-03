/*
 * This file is part of Invenio.
 * Copyright (C) 2014, 2015, 2016 CERN.
 *
 * Invenio is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Invenio is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Invenio. If not, see <http://www.gnu.org/licenses/>.
 *
 * In applying this licence, CERN does not waive the privileges and immunities
 * granted to it by virtue of its status as an Intergovernmental Organization
 * or submit itself to any jurisdiction.
 */
define(function(require, exports, module) {
  'use strict';

  var $ = require('jquery');
  require('node_modules/bootstrap-switch/dist/js/bootstrap-switch');

  return function(config) {
    init_switches(config);
    init_syncbutton(config);

    $('[data-toggle="tooltip"]').tooltip();

    $('i.error').tooltip({
      trigger: 'hover',
      animation: true,
      placement: 'top',
    });
  };

  function init_syncbutton(config){
    var syncButton = $(config.sync_button);

    syncButton.on('click', function() {
      syncButton.prop('disabled', true);
      $.ajax({
        url: config.sync_url,
        type: 'POST'
      })
      .done(function(data) {
        $(config.github_view).html(data);
        init_switches(config);
        init_syncbutton(config);
      })
      .always(function() {
        syncButton.prop('disabled', false);
      });
    });
  }

  function init_switches(config){
    // Initialize bootstrap switches
    var test_switch = $('input[name="test-flip"]').bootstrapSwitch();
    var doiSwitches = $('input[data-repo-id]').bootstrapSwitch();

    doiSwitches.on('switchChange.bootstrapSwitch', function(e, state) {
      // Disable the switch
      var $switch = $(e.target);
      $switch.bootstrapSwitch('disabled', true);
      var repoId = e.target.dataset.repoId;
      var method = state ? 'POST' : 'DELETE';

      $.ajax({
        url: config.hook_url,
        type: method,
        data: JSON.stringify({id: repoId}),
        contentType: 'application/json; charset=utf-8',
        dataType: 'json'
      })
      .done(function(data, textStatus, jqXHR) {
        var status = 'fa-exclamation text-warning';
        if(jqXHR.status == 204 || jqXHR.status==201){
          status =  'fa-check text-success';
        }

        // Select the correct hook status
        var el = $('[data-repo-id="' + repoId + '"].hook-status');
        el.addClass(status);
        el.animate({
          opacity: 0
        }, 2000, function() {
          el.removeClass(status);
          el.css('opacity', 1);
        });
      })
      .fail(function() {
        // Revert back to normal
        $switch.bootstrapSwitch('state', !state);
      })
      .always(function() {
        // Enable the switch
        $switch.bootstrapSwitch('disabled', false);
      });
    });
  }
});
